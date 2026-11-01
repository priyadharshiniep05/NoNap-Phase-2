import 'package:flutter/material.dart';
import 'package:phosphor_flutter/phosphor_flutter.dart';

import '../core/ist.dart';
import '../models/alert_item.dart';
import '../theme/tokens.dart';
import '../theme/typography.dart';
import 'ui.dart';

/// One alert on a vertical timeline: severity dot, IST time, level, acknowledgement.
class AlertTimelineEntry extends StatelessWidget {
  final AlertItem alert;
  final bool last;
  final bool driverView; // "You were drowsy" vs "Drowsy"
  const AlertTimelineEntry({super.key, required this.alert, required this.last, this.driverView = true});

  @override
  Widget build(BuildContext context) {
    final color = AppColors.forLevel(alert.effectiveLevel);
    final ack = alert.acknowledged
        ? (alert.responseTimeMs != null ? 'Acknowledged in ${Ist.duration(alert.responseTimeMs)}' : 'Acknowledged')
        : (alert.status == 'resolved' ? 'Cleared on its own' : 'Not acknowledged');
    return IntrinsicHeight(
      child: Row(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        SizedBox(
          width: 22,
          child: Column(children: [
            const SizedBox(height: 18),
            StatusDot(color: color, size: 10),
            if (!last) Expanded(child: Container(width: 1.5, margin: const EdgeInsets.only(top: 4), color: AppColors.border)),
          ]),
        ),
        const SizedBox(width: AppSpace.s),
        Expanded(
          child: Padding(
            padding: const EdgeInsets.only(bottom: AppSpace.m),
            child: Semantics(
              label: alert.historyLine,
              child: GlassCard(
                blur: false,
                padding: const EdgeInsets.all(AppSpace.l),
                child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Row(children: [
                    Text(Ist.hmIst(alert.detectedAt), style: AppText.metric(size: 18)),
                    const SizedBox(width: AppSpace.s),
                    LevelChip(alert.effectiveLevel),
                    const Spacer(),
                    if (alert.isSimulated) const Pill('Simulated', color: AppColors.textMuted),
                  ]),
                  const SizedBox(height: AppSpace.s),
                  Text(
                    driverView
                        ? '${alert.type == 'yawning' ? 'You were yawning' : 'You were drowsy'} · ${alert.reasonLabel}'
                        : alert.reasonLabel,
                    style: AppText.body(color: AppColors.textPrimary).copyWith(fontSize: 14),
                  ),
                  const SizedBox(height: 2),
                  Row(children: [
                    Icon(
                      alert.acknowledged ? PhosphorIconsFill.checkCircle : PhosphorIconsRegular.clock,
                      size: 14,
                      color: alert.acknowledged ? AppColors.success : AppColors.textMuted,
                    ),
                    const SizedBox(width: 6),
                    Text(ack, style: AppText.caption()),
                    if (alert.escalatedAt != null) ...[
                      const SizedBox(width: AppSpace.s),
                      Text('· manager notified', style: AppText.caption(color: AppColors.danger)),
                    ],
                  ]),
                ]),
              ),
            ),
          ),
        ),
      ]),
    );
  }
}
