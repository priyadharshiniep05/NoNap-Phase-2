class User {
  final String id;
  final String fullName;
  final String email;
  final String role; // 'driver' or 'fleet_manager'
  final String? fleetId;

  User({
    required this.id,
    required this.fullName,
    required this.email,
    required this.role,
    this.fleetId,
  });

  bool get isDriver => role == 'driver';
  bool get isFleetManager => role == 'fleet_manager';

  factory User.fromJson(Map<String, dynamic> json) {
    return User(
      id: json['id'] as String,
      fullName: json['full_name'] as String,
      email: json['email'] as String,
      role: json['role'] as String,
      fleetId: json['fleet_id'] as String?,
    );
  }

  Map<String, dynamic> toJson() => {
    'id': id,
    'full_name': fullName,
    'email': email,
    'role': role,
    'fleet_id': fleetId,
  };
}
