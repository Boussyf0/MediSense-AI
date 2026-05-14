import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../../core/api/dio_client.dart';
import '../../data/datasources/patient_remote_datasource.dart';

final patientDatasourceProvider =
    Provider((ref) => PatientRemoteDatasource(createDio()));
