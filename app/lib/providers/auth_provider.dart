import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/user.dart';
import '../services/api_service.dart';
import '../services/ws_service.dart';

final apiServiceProvider = Provider<ApiService>((ref) => ApiService());
final wsServiceProvider = Provider<WebSocketService>((ref) => WebSocketService());

/// Live WebSocket status for the connection indicators.
final wsStatusProvider = StreamProvider<WsStatus>((ref) async* {
  final ws = ref.watch(wsServiceProvider);
  yield ws.status;
  yield* ws.statusStream;
});

class AuthState {
  final User? user;
  final bool isLoading;
  final bool booting; // first auth check after launch (splash)
  final String? error;

  AuthState({this.user, this.isLoading = false, this.booting = false, this.error});

  bool get isAuthenticated => user != null;
  bool get isDriver => user?.isDriver ?? false;
  bool get isFleetManager => user?.isFleetManager ?? false;

  AuthState copyWith({User? user, bool? isLoading, bool? booting, String? error, bool clearUser = false}) {
    return AuthState(
      user: clearUser ? null : (user ?? this.user),
      isLoading: isLoading ?? this.isLoading,
      booting: booting ?? this.booting,
      error: error,
    );
  }
}

class AuthNotifier extends StateNotifier<AuthState> {
  final ApiService _api;
  final WebSocketService _ws;

  AuthNotifier(this._api, this._ws) : super(AuthState(isLoading: true, booting: true)) {
    checkAuth();
  }

  Future<void> checkAuth() async {
    final started = DateTime.now();
    state = state.copyWith(isLoading: true, error: null);
    try {
      await _api.init();
      if (_api.token != null && _api.hasServer) {
        final user = await _api.getMe();
        _connectWs(user);
        state = state.copyWith(user: user);
      } else {
        state = state.copyWith(clearUser: true);
      }
    } catch (e) {
      // Only forget the session when the server says the token is bad,
      // not when the Mac is simply unreachable right now.
      if (e is DioException && e.response?.statusCode == 401) await _api.logout();
      state = state.copyWith(clearUser: true);
    }
    // Let the splash animation finish (it is short, and skipped with reduced motion).
    final elapsed = DateTime.now().difference(started);
    if (elapsed < const Duration(milliseconds: 1100)) {
      await Future.delayed(const Duration(milliseconds: 1100) - elapsed);
    }
    state = state.copyWith(isLoading: false, booting: false);
  }

  Future<bool> login(String email, String password) async {
    state = state.copyWith(isLoading: true, error: null);
    try {
      if (!_api.hasServer) throw StateError('no server');
      await _api.login(email, password);
      final user = await _api.getMe();
      _connectWs(user);
      state = state.copyWith(user: user, isLoading: false);
      return true;
    } catch (e) {
      String msg;
      if (e is StateError) {
        msg = 'Set the NoNap server address first (tap Server).';
      } else if (e is DioException && e.response?.statusCode == 401) {
        msg = 'That email and password do not match.';
      } else {
        msg = friendlyError(e);
      }
      state = state.copyWith(isLoading: false, error: msg);
      return false;
    }
  }

  Future<bool> signup({
    required String fullName,
    required String email,
    required String password,
    required String role,
  }) async {
    state = state.copyWith(isLoading: true, error: null);
    try {
      if (!_api.hasServer) throw StateError('no server');
      await _api.signup(fullName: fullName, email: email, password: password, role: role);
      return await login(email, password);
    } catch (e) {
      String msg = friendlyError(e);
      if (e is StateError) msg = 'Set the NoNap server address first (tap Server).';
      state = state.copyWith(isLoading: false, error: msg);
      return false;
    }
  }

  Future<void> logout() async {
    _ws.stop();
    await _api.logout();
    state = state.copyWith(clearUser: true, isLoading: false, error: null);
  }

  void _connectWs(User user) {
    final path = user.isDriver ? '/ws/driver/${user.id}' : '/ws/fleet/${user.id}';
    _ws.start(path: path, baseUrl: () => _api.baseUrl, token: _api.validAccessToken);
  }
}

final authProvider = StateNotifierProvider<AuthNotifier, AuthState>((ref) {
  return AuthNotifier(ref.watch(apiServiceProvider), ref.watch(wsServiceProvider));
});
