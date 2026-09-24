import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../models/user.dart';
import '../services/api_service.dart';
import '../services/ws_service.dart';

final apiServiceProvider = Provider<ApiService>((ref) => ApiService());
final wsServiceProvider = Provider<WebSocketService>((ref) => WebSocketService());

class AuthState {
  final User? user;
  final bool isLoading;
  final String? error;

  AuthState({this.user, this.isLoading = false, this.error});

  bool get isAuthenticated => user != null;
  bool get isDriver => user?.isDriver ?? false;
  bool get isFleetManager => user?.isFleetManager ?? false;

  AuthState copyWith({User? user, bool? isLoading, String? error, bool clearUser = false}) {
    return AuthState(
      user: clearUser ? null : (user ?? this.user),
      isLoading: isLoading ?? this.isLoading,
      error: error,
    );
  }
}

class AuthNotifier extends StateNotifier<AuthState> {
  final ApiService _api;
  final WebSocketService _ws;

  AuthNotifier(this._api, this._ws) : super(AuthState(isLoading: true)) {
    checkAuth();
  }

  Future<void> checkAuth() async {
    state = state.copyWith(isLoading: true, error: null);
    try {
      await _api.init();
      if (_api.token != null) {
        final user = await _api.getMe();
        _connectWs(user);
        state = state.copyWith(user: user, isLoading: false);
      } else {
        state = state.copyWith(clearUser: true, isLoading: false);
      }
    } catch (e) {
      await _api.logout();
      state = state.copyWith(clearUser: true, isLoading: false);
    }
  }

  Future<bool> login(String email, String password) async {
    state = state.copyWith(isLoading: true, error: null);
    try {
      await _api.login(email, password);
      final user = await _api.getMe();
      _connectWs(user);
      state = state.copyWith(user: user, isLoading: false);
      return true;
    } catch (e) {
      state = state.copyWith(
        isLoading: false,
        error: 'Invalid credentials or connection error.',
      );
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
      await _api.signup(fullName: fullName, email: email, password: password, role: role);
      // Auto login after signup
      return await login(email, password);
    } catch (e) {
      state = state.copyWith(
        isLoading: false,
        error: 'Signup failed. Check details or email may already exist.',
      );
      return false;
    }
  }

  Future<void> logout() async {
    _ws.disconnect();
    await _api.logout();
    state = state.copyWith(clearUser: true, isLoading: false, error: null);
  }

  void _connectWs(User user) {
    if (_api.token != null) {
      _ws.connect(baseUrl: _api.baseUrl, token: _api.token!);
    }
  }
}

final authProvider = StateNotifierProvider<AuthNotifier, AuthState>((ref) {
  final api = ref.watch(apiServiceProvider);
  final ws = ref.watch(wsServiceProvider);
  return AuthNotifier(api, ws);
});
