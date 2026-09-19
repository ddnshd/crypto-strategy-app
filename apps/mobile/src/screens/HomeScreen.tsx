import React, {useEffect, useState} from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  RefreshControl,
  ActivityIndicator,
} from 'react-native';
import {useStore} from '../store';
import {signalsApi} from '../api/signals';

const COLORS = {
  bg: '#0D1117',
  surface: '#161B22',
  border: '#30363D',
  primary: '#58A6FF',
  success: '#3FB950',
  danger: '#F85149',
  warning: '#D29922',
  text: '#E6EDF3',
  textMuted: '#8B949E',
};

export default function HomeScreen() {
  const {strategies, signals, loadStrategies, loadSignals, loadScanners, scanners} = useStore();
  const [refreshing, setRefreshing] = useState(false);
  const [stats, setStats] = useState<any>(null);

  useEffect(() => {
    loadStrategies();
    loadSignals();
    loadScanners();
    fetchStats();
  }, []);

  const fetchStats = async () => {
    try {
      const s = await signalsApi.getStats();
      setStats(s);
    } catch {}
  };

  const onRefresh = async () => {
    setRefreshing(true);
    await Promise.all([loadStrategies(), loadSignals(), loadScanners(), fetchStats()]);
    setRefreshing(false);
  };

  const activeStrategies = strategies.filter(s => s.is_active);
  const qualifiedStrategies = strategies.filter(s => s.is_backtested && s.backtest_score && s.backtest_score >= 50);
  const recentSignals = signals.slice(0, 5);

  return (
    <ScrollView
      style={styles.container}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={COLORS.primary} />}>
      {/* Summary Stats */}
      <View style={styles.statsGrid}>
        <StatCard
          label="Total Strategi"
          value={strategies.length.toString()}
          color={COLORS.primary}
        />
        <StatCard
          label="Aktif"
          value={activeStrategies.length.toString()}
          color={COLORS.success}
        />
        <StatCard
          label="Qualified"
          value={qualifiedStrategies.length.toString()}
          color={COLORS.warning}
        />
        <StatCard
          label="Total Sinyal"
          value={stats?.total_signals?.toString() ?? '0'}
          color={COLORS.textMuted}
        />
      </View>

      {/* Signal Performance */}
      {stats && stats.total_signals > 0 && (
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Performa Sinyal</Text>
          <View style={styles.card}>
            <PerformanceRow
              label="Hit Rate (sinyal valid)"
              value={stats.hit_rate ? `${(stats.hit_rate * 100).toFixed(1)}%` : '-'}
              color={stats.hit_rate > 0.5 ? COLORS.success : COLORS.danger}
            />
            <PerformanceRow
              label="Avg PnL per Sinyal"
              value={stats.avg_pnl_pct ? `${stats.avg_pnl_pct > 0 ? '+' : ''}${stats.avg_pnl_pct.toFixed(2)}%` : '-'}
              color={stats.avg_pnl_pct > 0 ? COLORS.success : COLORS.danger}
            />
            <PerformanceRow
              label="W / L"
              value={`${stats.wins} / ${stats.losses}`}
              color={COLORS.text}
            />
          </View>
        </View>
      )}

      {/* Active Scanners */}
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Scanner Aktif ({scanners.filter(s => s.is_active).length})</Text>
        {scanners.filter(s => s.is_active).length === 0 ? (
          <View style={styles.emptyCard}>
            <Text style={styles.emptyText}>Belum ada scanner aktif</Text>
            <Text style={styles.emptySubtext}>
              Buat strategi di Builder, lakukan backtest, lalu aktifkan scanner
            </Text>
          </View>
        ) : (
          scanners.filter(s => s.is_active).map(scanner => {
            const strategy = strategies.find(s => s.id === scanner.strategy_id);
            return (
              <View key={scanner.id} style={styles.scannerItem}>
                <View style={styles.scannerDot} />
                <View style={{flex: 1}}>
                  <Text style={styles.scannerName}>{strategy?.name ?? 'Unknown'}</Text>
                  <Text style={styles.scannerMeta}>
                    {strategy?.pair} {strategy?.timeframe} •{' '}
                    {scanner.last_checked_at
                      ? `Cek terakhir: ${new Date(scanner.last_checked_at).toLocaleTimeString('id-ID')}`
                      : 'Menunggu...'}
                  </Text>
                </View>
                <View style={styles.activeBadge}>
                  <Text style={styles.activeBadgeText}>LIVE</Text>
                </View>
              </View>
            );
          })
        )}
      </View>

      {/* Recent Signals */}
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Sinyal Terbaru</Text>
        {recentSignals.length === 0 ? (
          <View style={styles.emptyCard}>
            <Text style={styles.emptyText}>Belum ada sinyal</Text>
          </View>
        ) : (
          recentSignals.map(signal => (
            <View key={signal.id} style={styles.signalItem}>
              <View style={[styles.directionBadge, {backgroundColor: signal.direction === 'long' ? '#1B4332' : '#4C0519'}]}>
                <Text style={[styles.directionText, {color: signal.direction === 'long' ? COLORS.success : COLORS.danger}]}>
                  {signal.direction.toUpperCase()}
                </Text>
              </View>
              <View style={{flex: 1, marginLeft: 10}}>
                <Text style={styles.signalPair}>{signal.pair}</Text>
                <Text style={styles.signalMeta}>
                  Entry: {signal.entry_price.toFixed(4)}
                  {signal.take_profit ? ` | TP: ${signal.take_profit.toFixed(4)}` : ''}
                  {signal.stop_loss ? ` | SL: ${signal.stop_loss.toFixed(4)}` : ''}
                </Text>
                <Text style={styles.signalTime}>
                  {new Date(signal.triggered_at).toLocaleString('id-ID')}
                </Text>
              </View>
              {signal.is_hit !== null && signal.is_hit !== undefined && (
                <Text style={{color: signal.is_hit ? COLORS.success : COLORS.danger, fontSize: 12, fontWeight: '700'}}>
                  {signal.is_hit ? `+${signal.pnl_pct?.toFixed(2)}%` : `${signal.pnl_pct?.toFixed(2)}%`}
                </Text>
              )}
            </View>
          ))
        )}
      </View>
    </ScrollView>
  );
}

function StatCard({label, value, color}: {label: string; value: string; color: string}) {
  return (
    <View style={[styles.statCard, {borderTopColor: color}]}>
      <Text style={[styles.statValue, {color}]}>{value}</Text>
      <Text style={styles.statLabel}>{label}</Text>
    </View>
  );
}

function PerformanceRow({label, value, color}: {label: string; value: string; color: string}) {
  return (
    <View style={styles.perfRow}>
      <Text style={styles.perfLabel}>{label}</Text>
      <Text style={[styles.perfValue, {color}]}>{value}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {flex: 1, backgroundColor: COLORS.bg},
  statsGrid: {flexDirection: 'row', flexWrap: 'wrap', padding: 12, gap: 8},
  statCard: {
    flex: 1,
    minWidth: '45%',
    backgroundColor: COLORS.surface,
    borderRadius: 8,
    padding: 14,
    borderTopWidth: 3,
  },
  statValue: {fontSize: 28, fontWeight: '700'},
  statLabel: {fontSize: 12, color: COLORS.textMuted, marginTop: 2},
  section: {marginHorizontal: 12, marginBottom: 16},
  sectionTitle: {fontSize: 16, fontWeight: '700', color: COLORS.text, marginBottom: 8},
  card: {backgroundColor: COLORS.surface, borderRadius: 10, padding: 14, borderWidth: 1, borderColor: COLORS.border},
  emptyCard: {
    backgroundColor: COLORS.surface,
    borderRadius: 10,
    padding: 20,
    alignItems: 'center',
    borderWidth: 1,
    borderColor: COLORS.border,
  },
  emptyText: {color: COLORS.textMuted, fontSize: 14, fontWeight: '600'},
  emptySubtext: {color: COLORS.textMuted, fontSize: 12, marginTop: 4, textAlign: 'center'},
  perfRow: {flexDirection: 'row', justifyContent: 'space-between', paddingVertical: 6},
  perfLabel: {color: COLORS.textMuted, fontSize: 13},
  perfValue: {fontSize: 14, fontWeight: '700'},
  scannerItem: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: COLORS.surface,
    borderRadius: 8,
    padding: 12,
    marginBottom: 6,
    borderWidth: 1,
    borderColor: COLORS.border,
  },
  scannerDot: {width: 8, height: 8, borderRadius: 4, backgroundColor: COLORS.success, marginRight: 10},
  scannerName: {color: COLORS.text, fontWeight: '600', fontSize: 14},
  scannerMeta: {color: COLORS.textMuted, fontSize: 11, marginTop: 2},
  activeBadge: {backgroundColor: '#1B4332', paddingHorizontal: 6, paddingVertical: 2, borderRadius: 4},
  activeBadgeText: {color: COLORS.success, fontSize: 10, fontWeight: '800'},
  signalItem: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: COLORS.surface,
    borderRadius: 8,
    padding: 10,
    marginBottom: 6,
    borderWidth: 1,
    borderColor: COLORS.border,
  },
  directionBadge: {paddingHorizontal: 6, paddingVertical: 3, borderRadius: 4},
  directionText: {fontWeight: '800', fontSize: 11},
  signalPair: {color: COLORS.text, fontWeight: '600', fontSize: 14},
  signalMeta: {color: COLORS.textMuted, fontSize: 11, marginTop: 2},
  signalTime: {color: COLORS.textMuted, fontSize: 10, marginTop: 2},
});
