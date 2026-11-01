import 'dart:convert';

import 'package:dio/dio.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

import '../models/alert_item.dart';
import '../models/device_status.dart';
import '../models/fleet_overview.dart';
import '../models/session_info.dart';
import '../models/user.dart';

/// REST client for the NoNap backend.
///
/// The server address is never hard-coded: it comes from the value saved in
/// the server dialog, else `--dart-define=API_BASE_URL=http://<mac-ip>:8000`.
/// Access tokens expire after 15 minutes, so a 401 triggers one silent
/// refresh with the stored refresh token and a retry.
class ApiService {
  static final ApiService _instance = ApiService._internal();
  factory ApiService() => _instance;
  ApiService._internal() {
    _dio.interceptors.add(QueuedInterceptorsWrapper(onError: _onError));
  }

  static const _kBase = 'nonap_base_url';
  static const _kRecent = 'nonap_recent_servers';
  static const _kAccess = 'nonap_access_token';
  static const _kRefresh = 'nonap_refresh_token';

  final FlutterSecureStorage _storage = const FlutterSecureStorage();
  final Dio _dio = Dio(BaseOptions(
    connectTimeout: const Duration(seconds: 5),
    receiveTimeout: const Duration(seconds: 10),
    contentType: Headers.jsonContentType,
  ));

  String _baseUrl = const String.fromEnvironment('API_BASE_URL', defaultValue: '');
  String? _token;
  String? _refreshToken;

  String get baseUrl => _baseUrl;
  bool get hasServer => _baseUrl.isNotEmpty;
  String? get token => _token;

  Future<void> init() async {
    final saved = await _storage.read(key: _kBase);
    if (saved != null && saved.isNotEmpty) _baseUrl = saved;
    _token = await _storage.read(key: _kAccess);
    _refreshToken = await _storage.read(key: _kRefresh);
  }

  String _clean(String url) {
    var u = url.trim().replaceAll(RegExp(r'/+$'), '');
    if (u.isNotEmpty && !u.startsWith('http')) u = 'http://$u';
    return u;
  }

  Future<bool> checkHealth([String? url]) async {
    final target = _clean(url ?? _baseUrl);
    if (target.isEmpty) return false;
    try {
      final res = await _dio.get('$target/health',
          options: Options(sendTimeout: const Duration(seconds: 2), receiveTimeout: const Duration(seconds: 2)));
      return res.statusCode == 200;
    } catch (_) {
      return false;
    }
  }

  Future<void> setBaseUrl(String url) async {
    _baseUrl = _clean(url);
    await _storage.write(key: _kBase, value: _baseUrl);
    final recent = await recentServers();
    final next = [_baseUrl, ...recent.where((r) => r != _baseUrl)].take(4).toList();
    await _storage.write(key: _kRecent, value: jsonEncode(next));
  }

  Future<List<String>> recentServers() async {
    try {
      final raw = await _storage.read(key: _kRecent);
      if (raw == null) return [];
      return (jsonDecode(raw) as List).cast<String>();
    } catch (_) {
      return [];
    }
  }

  Future<void> _saveTokens(String? access, String? refresh) async {
    _token = access;
    _refreshToken = refresh;
    if (access == null) {
      await _storage.delete(key: _kAccess);
      await _storage.delete(key: _kRefresh);
    } else {
      await _storage.write(key: _kAccess, value: access);
      if (refresh != null) await _storage.write(key: _kRefresh, value: refresh);
    }
  }

  Options get _auth => Options(headers: {if (_token != null) 'Authorization': 'Bearer $_token'});

  // ---- token refresh -------------------------------------------------------

  Future<bool> refreshTokens() async {
    if (_refreshToken == null || _baseUrl.isEmpty) return false;
    try {
      final res = await Dio(BaseOptions(connectTimeout: const Duration(seconds: 5)))
          .post('$_baseUrl/auth/refresh', data: {'refresh_token': _refreshToken});
      final data = res.data as Map<String, dynamic>;
      await _saveTokens(data['access_token'] as String, data['refresh_token'] as String?);
      return true;
    } catch (_) {
      return false;
    }
  }

  /// A token valid for at least another minute (refreshing first if needed);
  /// used before every WebSocket (re)connect.
  Future<String?> validAccessToken() async {
    if (_token == null) return null;
    final exp = _jwtExpiry(_token!);
    if (exp != null && exp.difference(DateTime.now()).inSeconds < 60) {
      await refreshTokens();
    }
    return _token;
  }

  DateTime? _jwtExpiry(String jwt) {
    try {
      final parts = jwt.split('.');
      final payload = jsonDecode(utf8.decode(base64Url.decode(base64Url.normalize(parts[1])))) as Map;
      final exp = payload['exp'] as num?;
      return exp == null ? null : DateTime.fromMillisecondsSinceEpoch(exp.toInt() * 1000);
    } catch (_) {
      return null;
    }
  }

  Future<void> _onError(DioException err, ErrorInterceptorHandler handler) async {
    final req = err.requestOptions;
    final isAuthCall = req.path.contains('/auth/');
    if (err.response?.statusCode == 401 && !isAuthCall && req.extra['retried'] != true) {
      if (await refreshTokens()) {
        req.headers['Authorization'] = 'Bearer $_token';
        req.extra['retried'] = true;
        try {
          return handler.resolve(await _dio.fetch(req));
        } on DioException catch (e) {
          return handler.next(e);
        }
      }
    }
    handler.next(err);
  }

  // ---- auth ----------------------------------------------------------------

  Future<void> login(String email, String password) async {
    final res = await _dio.post('$_baseUrl/auth/login',
        data: {'email': email.trim().toLowerCase(), 'password': password});
    final data = res.data as Map<String, dynamic>;
    await _saveTokens(data['access_token'] as String, data['refresh_token'] as String?);
  }

  Future<void> signup({
    required String fullName,
    required String email,
    required String password,
    required String role,
  }) async {
    await _dio.post('$_baseUrl/auth/signup', data: {
      'full_name': fullName.trim(),
      'email': email.trim().toLowerCase(),
      'password': password,
      'role': role,
    });
  }

  Future<User> getMe() async {
    final res = await _dio.get('$_baseUrl/auth/me', options: _auth);
    return User.fromJson(res.data as Map<String, dynamic>);
  }

  Future<void> logout() => _saveTokens(null, null);

  // ---- system --------------------------------------------------------------

  Future<Map<String, dynamic>> getSystem() async {
    final res = await _dio.get('$_baseUrl/api/v1/system');
    return res.data as Map<String, dynamic>;
  }

  // ---- driver --------------------------------------------------------------

  Future<Map<String, dynamic>> getDriverStats() async {
    final res = await _dio.get('$_baseUrl/driver/stats', options: _auth);
    return res.data as Map<String, dynamic>;
  }

  Future<List<AlertItem>> getDriverAlerts({int limit = 100}) async {
    final res = await _dio.get('$_baseUrl/driver/alerts', queryParameters: {'limit': limit}, options: _auth);
    return (res.data as List).map((j) => AlertItem.fromJson(j as Map<String, dynamic>)).toList();
  }

  Future<Map<String, dynamic>> getDriverThresholds() async {
    final res = await _dio.get('$_baseUrl/driver/thresholds', options: _auth);
    return res.data as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> updateDriverThresholds(Map<String, dynamic> data) async {
    final res = await _dio.put('$_baseUrl/driver/thresholds', data: data, options: _auth);
    return res.data as Map<String, dynamic>;
  }

  Future<SessionInfo> getSession() async {
    final res = await _dio.get('$_baseUrl/api/v1/driver/session', options: _auth);
    return SessionInfo.fromJson(res.data as Map<String, dynamic>);
  }

  Future<SessionInfo> startSession() async {
    final res = await _dio.post('$_baseUrl/api/v1/driver/session/start', options: _auth);
    return SessionInfo.fromJson(res.data as Map<String, dynamic>);
  }

  Future<SessionInfo> endSession() async {
    final res = await _dio.post('$_baseUrl/api/v1/driver/session/end', options: _auth);
    return SessionInfo.fromJson(res.data as Map<String, dynamic>);
  }

  /// ({video_source, device})
  Future<(String, DeviceStatus?)> getMyDevice() async {
    final res = await _dio.get('$_baseUrl/api/v1/driver/device', options: _auth);
    final data = res.data as Map<String, dynamic>;
    final dev = data['device'] as Map<String, dynamic>?;
    return (data['video_source'] as String? ?? 'pi', dev != null ? DeviceStatus.fromJson(dev) : null);
  }

  Future<AlertItem> acknowledgeAlert(String alertId) async {
    final res = await _dio.post('$_baseUrl/api/v1/alerts/$alertId/ack',
        options: _auth.copyWith(sendTimeout: const Duration(seconds: 4), receiveTimeout: const Duration(seconds: 4)));
    return AlertItem.fromJson(res.data as Map<String, dynamic>);
  }

  Future<void> startCalibration({double duration = 10.0}) async {
    await _dio.post('$_baseUrl/driver/calibrate/start', queryParameters: {'duration': duration}, options: _auth);
  }

  Future<Map<String, dynamic>> getCalibrationStatus() async {
    final res = await _dio.get('$_baseUrl/driver/calibrate/status', options: _auth);
    return res.data as Map<String, dynamic>;
  }

  Future<void> reportAccidentSos({String? driverId}) async {
    await _dio.post('$_baseUrl/alerts/accident', data: {'driver_id': driverId, 'confidence': 1.0}, options: _auth);
  }

  // ---- fleet ---------------------------------------------------------------

  Future<FleetOverview> getFleetOverview() async {
    final res = await _dio.get('$_baseUrl/fleet/overview', options: _auth);
    return FleetOverview.fromJson(res.data as Map<String, dynamic>);
  }

  Future<List<AlertItem>> getFleetAlerts({int limit = 60}) async {
    final res = await _dio.get('$_baseUrl/fleet/alerts', queryParameters: {'limit': limit}, options: _auth);
    return (res.data as List).map((j) => AlertItem.fromJson(j as Map<String, dynamic>)).toList();
  }

  Future<List<AlertItem>> getFleetDriverAlerts(String driverId, {int limit = 100}) async {
    final res = await _dio.get('$_baseUrl/fleet/drivers/$driverId/alerts',
        queryParameters: {'limit': limit}, options: _auth);
    return (res.data as List).map((j) => AlertItem.fromJson(j as Map<String, dynamic>)).toList();
  }

  Future<Map<String, dynamic>> getFleetThresholds() async {
    final res = await _dio.get('$_baseUrl/fleet/thresholds', options: _auth);
    return res.data as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> updateFleetThresholds(Map<String, dynamic> data) async {
    final res = await _dio.put('$_baseUrl/fleet/thresholds', data: data, options: _auth);
    return res.data as Map<String, dynamic>;
  }
}

/// Turn any error into one friendly sentence (never raw exception text).
String friendlyError(Object e) {
  if (e is DioException) {
    switch (e.type) {
      case DioExceptionType.connectionTimeout:
      case DioExceptionType.connectionError:
      case DioExceptionType.sendTimeout:
      case DioExceptionType.receiveTimeout:
        return "Can't reach the NoNap server. Check that the Mac is on the same network.";
      case DioExceptionType.badResponse:
        final code = e.response?.statusCode ?? 0;
        final detail = e.response?.data is Map ? (e.response!.data as Map)['detail'] : null;
        if (code == 401) return 'Your session expired. Please sign in again.';
        if (code == 403) return "This account can't open that screen.";
        if (detail is String && detail.length < 140) return detail;
        return 'The server could not complete that request ($code).';
      default:
        break;
    }
  }
  return 'Something went wrong. Please try again.';
}
