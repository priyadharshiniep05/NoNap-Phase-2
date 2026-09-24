import 'package:dio/dio.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import '../models/user.dart';
import '../models/alert_item.dart';
import '../models/fleet_overview.dart';

class ApiService {
  static final ApiService _instance = ApiService._internal();
  factory ApiService() => _instance;
  ApiService._internal();

  final FlutterSecureStorage _storage = const FlutterSecureStorage();
  late final Dio _dio = Dio(
    BaseOptions(
      connectTimeout: const Duration(seconds: 5),
      receiveTimeout: const Duration(seconds: 10),
    ),
  );

  String _baseUrl = 'http://localhost:8000';
  String? _token;

  String get baseUrl => _baseUrl;
  String? get token => _token;

  Future<void> init() async {
    final savedBase = await _storage.read(key: 'nonap_base_url');
    if (savedBase != null && savedBase.isNotEmpty) {
      _baseUrl = savedBase;
    }
    _token = await _storage.read(key: 'nonap_access_token');
  }

  Future<void> setBaseUrl(String url) async {
    _baseUrl = url.replaceAll(RegExp(r'/+$'), '');
    await _storage.write(key: 'nonap_base_url', value: _baseUrl);
  }

  Future<void> setToken(String? token) async {
    _token = token;
    if (token != null) {
      await _storage.write(key: 'nonap_access_token', value: token);
    } else {
      await _storage.delete(key: 'nonap_access_token');
    }
  }

  Options _authOptions() {
    return Options(
      headers: {
        'Content-Type': 'application/json',
        if (_token != null) 'Authorization': 'Bearer $_token',
      },
    );
  }

  // --- Auth ---

  Future<Map<String, dynamic>> login(String email, String password) async {
    final response = await _dio.post(
      '$_baseUrl/auth/login',
      data: {'email': email.trim().toLowerCase(), 'password': password},
    );
    final data = response.data as Map<String, dynamic>;
    final token = data['access_token'] as String;
    await setToken(token);
    return data;
  }

  Future<Map<String, dynamic>> signup({
    required String fullName,
    required String email,
    required String password,
    required String role,
  }) async {
    final response = await _dio.post(
      '$_baseUrl/auth/signup',
      data: {
        'full_name': fullName.trim(),
        'email': email.trim().toLowerCase(),
        'password': password,
        'role': role,
      },
    );
    return response.data as Map<String, dynamic>;
  }

  Future<User> getMe() async {
    final response = await _dio.get('$_baseUrl/auth/me', options: _authOptions());
    return User.fromJson(response.data as Map<String, dynamic>);
  }

  Future<void> logout() async {
    await setToken(null);
  }

  // --- Driver Endpoints ---

  Future<Map<String, dynamic>> getDriverStats() async {
    final response = await _dio.get('$_baseUrl/driver/stats', options: _authOptions());
    return response.data as Map<String, dynamic>;
  }

  Future<List<AlertItem>> getDriverAlerts({int limit = 50}) async {
    final response = await _dio.get(
      '$_baseUrl/driver/alerts?limit=$limit',
      options: _authOptions(),
    );
    final list = response.data as List<dynamic>;
    return list.map((item) => AlertItem.fromJson(item as Map<String, dynamic>)).toList();
  }

  Future<Map<String, dynamic>> getDriverThresholds() async {
    final response = await _dio.get('$_baseUrl/driver/thresholds', options: _authOptions());
    return response.data as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> updateDriverThresholds(Map<String, dynamic> data) async {
    final response = await _dio.put(
      '$_baseUrl/driver/thresholds',
      data: data,
      options: _authOptions(),
    );
    return response.data as Map<String, dynamic>;
  }

  // --- Fleet Endpoints ---

  Future<FleetOverview> getFleetOverview() async {
    final response = await _dio.get('$_baseUrl/fleet/overview', options: _authOptions());
    return FleetOverview.fromJson(response.data as Map<String, dynamic>);
  }

  Future<List<AlertItem>> getFleetAlerts({int limit = 100}) async {
    final response = await _dio.get(
      '$_baseUrl/fleet/alerts?limit=$limit',
      options: _authOptions(),
    );
    final list = response.data as List<dynamic>;
    return list.map((item) => AlertItem.fromJson(item as Map<String, dynamic>)).toList();
  }

  Future<Map<String, dynamic>> getFleetThresholds() async {
    final response = await _dio.get('$_baseUrl/fleet/thresholds', options: _authOptions());
    return response.data as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> updateFleetThresholds(Map<String, dynamic> data) async {
    final response = await _dio.put(
      '$_baseUrl/fleet/thresholds',
      data: data,
      options: _authOptions(),
    );
    return response.data as Map<String, dynamic>;
  }

  // --- Monitoring & SOS ---

  Future<void> startMonitoring({String? driverId}) async {
    await _dio.post(
      '$_baseUrl/monitor/start',
      data: {'driver_id': driverId},
      options: _authOptions(),
    );
  }

  Future<void> stopMonitoring() async {
    await _dio.post('$_baseUrl/monitor/stop', options: _authOptions());
  }

  Future<Map<String, dynamic>> getMonitorStatus() async {
    final response = await _dio.get('$_baseUrl/monitor/status');
    return response.data as Map<String, dynamic>;
  }

  Future<void> reportAccidentSos({String? driverId}) async {
    await _dio.post(
      '$_baseUrl/alerts/accident',
      data: {'driver_id': driverId, 'confidence': 1.0},
      options: _authOptions(),
    );
  }
}
