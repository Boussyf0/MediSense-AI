class DoctorModel {
  final String uuid;
  final String displayName;
  final String email;
  final String? specialty;

  const DoctorModel({
    required this.uuid,
    required this.displayName,
    required this.email,
    this.specialty,
  });

  factory DoctorModel.fromJson(Map<String, dynamic> j) => DoctorModel(
        uuid: j['user_uuid'] as String,
        displayName: j['display_name'] as String? ?? 'Dr. —',
        email: j['email'] as String? ?? '',
        specialty: j['specialty'] as String?,
      );
}
