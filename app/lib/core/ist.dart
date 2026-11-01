import 'package:intl/intl.dart';

/// Every time NoNap shows is Indian Standard Time (UTC+05:30, no DST),
/// whatever time zone the phone is set to.
class Ist {
  Ist._();

  static const Duration offset = Duration(hours: 5, minutes: 30);

  /// A DateTime whose wall-clock fields read as IST. Only for formatting.
  static DateTime of(DateTime t) => t.toUtc().add(offset);

  static DateTime now() => of(DateTime.now());

  /// Parses server timestamps. Values without an offset are IST wall-clock
  /// (how ops_db stores them); values with an offset are converted.
  static DateTime? parse(String? s) {
    if (s == null || s.isEmpty) return null;
    final hasZone = RegExp(r'(Z|[+-]\d{2}:?\d{2})$').hasMatch(s);
    final parsed = DateTime.tryParse(hasZone ? s : '$s+05:30');
    return parsed?.toUtc();
  }

  /// 14:32
  static String hm(DateTime t) => DateFormat('HH:mm').format(of(t));

  /// 14:32:05
  static String hms(DateTime t) => DateFormat('HH:mm:ss').format(of(t));

  /// 14:32 IST
  static String hmIst(DateTime t) => '${hm(t)} IST';

  /// 21 Oct
  static String dayMonth(DateTime t) => DateFormat('d MMM').format(of(t));

  /// "Today", "Yesterday" or "Mon, 19 Oct", relative to IST days.
  static String dayLabel(DateTime t) {
    final d = of(t);
    final n = now();
    final day = DateTime(d.year, d.month, d.day);
    final today = DateTime(n.year, n.month, n.day);
    final diff = today.difference(day).inDays;
    if (diff == 0) return 'Today';
    if (diff == 1) return 'Yesterday';
    return DateFormat('EEE, d MMM').format(d);
  }

  /// IST hour of day 0-23.
  static int hour(DateTime t) => of(t).hour;

  static String greeting() {
    final h = now().hour;
    if (h < 5) return 'Good night';
    if (h < 12) return 'Good morning';
    if (h < 17) return 'Good afternoon';
    return 'Good evening';
  }

  /// "3.4 s" / "850 ms"
  static String duration(double? ms) {
    if (ms == null) return '—';
    if (ms < 1000) return '${ms.round()} ms';
    return '${(ms / 1000).toStringAsFixed(1)} s';
  }

  /// "1 h 05 m" / "12 m 30 s"
  static String clockSpan(int seconds) {
    final h = seconds ~/ 3600;
    final m = (seconds % 3600) ~/ 60;
    final s = seconds % 60;
    if (h > 0) return '$h h ${m.toString().padLeft(2, '0')} m';
    return '$m m ${s.toString().padLeft(2, '0')} s';
  }
}
