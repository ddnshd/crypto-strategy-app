import React, {useEffect, useState} from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  Alert,
  ActivityIndicator,
} from 'react-native';
import {RouteProp, useNavigation, useRoute} from '@react-navigation/native';
import {backtestApi} from '../api/backtest';
import {signalsApi} from '../api/signals';
import {useStore} from '../store';
import {BacktestResult} from '../types';

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

type RouteParams = {strategyId: string};

export default function BacktestScreen() {
  const route = useRoute<RouteProp<{Backtest: RouteParams}, 'Backtest'>>();
  const navigation = useNavigation<any>();
  const {strategyId} = route.params;
  const {strategies, updateStrategy, addBacktestResult, backtestResults} = useStore();

  const strategy = strategies.find(s => s.id === strategyId);
  const [running, setRunning] = useState(false);
  const [progress, setProgress] = useState(0);
  const [result, setResult] = useState<BacktestResult | null>(null);
  const [backtestId, setBacktestId] = useState<string | null>(null);
  const [activatingScanner, setActivatingScanner] = useState(false);

  const runBacktest = async () => {
    if (!strategy) return;
    setRunning(true);
    setProgress(0);
    setResult(null);

    try {
      const {backtest_id} = await backtestApi.run({strategy_id: strategyId});
      setBacktestId(backtest_id);

      const finalResult = await backtestApi.waitForResult(backtest_id, attempt => {
        setProgress(Math.min(95, attempt * 8));
      });

      setResult(finalResult);
      setProgress(100);
      addBacktestResult(finalResult);

      // Update strategy status in store
      if (strategy) {
        updateStrategy({
          ...strategy,
          is_backtested: true,
          backtest_score: finalResult.score,
        });
      }
    } catch (err: any) {
      Alert.alert('Backtest Gagal', err.message);
    } finally {
      setRunning(false);
    }
  };

  const activateScanner = async () => {
    if (!result?.is_qualified) return;
    setActivatingScanner(true);
    try {
      await signalsApi.activateScanner(strategyId);
      if (strategy) {
        updateStrategy({...strategy, is_active: true});
      }
      Alert.alert(
        'Scanner Aktif',
        `Scanner untuk "${strategy?.name}" sudah aktif. Kamu akan mendapat notifikasi saat ada sinyal.`,
        [{text: 'OK', onPress: () => navigation.navigate('Signals')}],
      );
    } catch (err: any) {
      Alert.alert('Gagal', err.message);
    } finally {
      setActivatingScanner(false);
    }
  };

  if (!strategy) {
    return (
      <View style={styles.container}>
        <Text style={{color: COLORS.textMuted}}>Strategi tidak ditemukan</Text>
      </View>
    );
  }

  return (
    <ScrollView style={styles.container}>
      {/* Strategy Info */}
      <View style={styles.infoCard}>
        <Text style={styles.strategyName}>{strategy.name}</Text>
        <Text style={styles.strategyMeta}>
          {strategy.pair} · {strategy.timeframe} · {strategy.style}
        </Text>
      </View>

      {/* Run Button */}
      {!running && !result && (
        <TouchableOpacity style={styles.runBtn} onPress={runBacktest}>
          <Text style={styles.runBtnText}>Jalankan Backtest</Text>
        </TouchableOpacity>
      )}

      {/* Progress */}
      {running && (
        <View style={styles.progressCard}>
          <ActivityIndicator color={COLORS.primary} size="large" />
          <Text style={styles.progressText}>
            Mengambil data historis & menjalankan simulasi...
          </Text>
          <View style={styles.progressBar}>
            <View style={[styles.progressFill, {width: `${progress}%`}]} />
          </View>
          <Text style={styles.progressPct}>{progress}%</Text>
        </View>
      )}

      {/* Results */}
      {result && (
        <>
          {/* Score Badge */}
          <View style={styles.scoreHeader}>
            <View
              style={[
                styles.scoreBadge,
                {
                  backgroundColor: result.is_qualified
                    ? '#1B4332'
                    : '#4C0519',
                  borderColor: result.is_qualified ? COLORS.success : COLORS.danger,
                },
              ]}>
              <Text style={[styles.scoreNum, {color: result.is_qualified ? COLORS.success : COLORS.danger}]}>
                {result.score.toFixed(0)}/100
              </Text>
              <Text style={[styles.scoreLabel, {color: result.is_qualified ? COLORS.success : COLORS.danger}]}>
                {result.is_qualified ? 'QUALIFIED ✓' : 'TIDAK QUALIFIED ✗'}
              </Text>
            </View>
          </View>

          {/* Key Metrics */}
          <View style={styles.metricsGrid}>
            <MetricBox label="Win Rate" value={`${(result.win_rate * 100).toFixed(1)}%`}
              color={result.win_rate >= 0.5 ? COLORS.success : COLORS.warning} />
            <MetricBox label="Profit Factor" value={result.profit_factor.toFixed(2)}
              color={result.profit_factor >= 1.5 ? COLORS.success : result.profit_factor >= 1 ? COLORS.warning : COLORS.danger} />
            <MetricBox label="Max Drawdown" value={`${(result.max_drawdown * 100).toFixed(1)}%`}
              color={result.max_drawdown <= 0.15 ? COLORS.success : COLORS.danger} />
            <MetricBox label="Total Return" value={`${result.total_return > 0 ? '+' : ''}${(result.total_return * 100).toFixed(1)}%`}
              color={result.total_return > 0 ? COLORS.success : COLORS.danger} />
            <MetricBox label="Total Trade" value={result.total_trades.toString()} color={COLORS.text} />
            <MetricBox label="Sharpe Ratio" value={result.sharpe_ratio?.toFixed(2) ?? '-'} color={COLORS.text} />
          </View>

          {/* W/L breakdown */}
          <View style={styles.wlCard}>
            <Text style={styles.sectionTitle}>Trade Breakdown</Text>
            <View style={styles.wlRow}>
              <View style={styles.wlItem}>
                <Text style={[styles.wlNum, {color: COLORS.success}]}>{result.winning_trades}</Text>
                <Text style={styles.wlLabel}>Win</Text>
              </View>
              <View style={styles.wlDivider} />
              <View style={styles.wlItem}>
                <Text style={[styles.wlNum, {color: COLORS.danger}]}>{result.losing_trades}</Text>
                <Text style={styles.wlLabel}>Loss</Text>
              </View>
              <View style={styles.wlDivider} />
              <View style={styles.wlItem}>
                <Text style={[styles.wlNum, {color: COLORS.text}]}>
                  {result.avg_rr?.toFixed(2) ?? '-'}
                </Text>
                <Text style={styles.wlLabel}>Avg R:R</Text>
              </View>
            </View>
          </View>

          {/* Walk Forward */}
          {result.walk_forward && (
            <View style={styles.wfCard}>
              <Text style={styles.sectionTitle}>Walk-Forward Analysis</Text>
              <Text style={styles.wfPeriod}>In-Sample: {result.walk_forward.in_sample.period}</Text>
              <WFRow label="Win Rate" inSample={result.walk_forward.in_sample.win_rate} outSample={result.walk_forward.out_of_sample.win_rate} format="pct" />
              <WFRow label="Profit Factor" inSample={result.walk_forward.in_sample.profit_factor} outSample={result.walk_forward.out_of_sample.profit_factor} format="num" />
              <WFRow label="Total Return" inSample={result.walk_forward.in_sample.total_return} outSample={result.walk_forward.out_of_sample.total_return} format="pct" />
              <View style={styles.degradRow}>
                <Text style={styles.wfLabel}>Degradasi PF</Text>
                <Text style={[styles.wfVal, {
                  color: result.walk_forward.degradation_pct <= 20 ? COLORS.success : COLORS.danger,
                }]}>
                  {result.walk_forward.degradation_pct.toFixed(1)}%
                </Text>
              </View>
            </View>
          )}

          {/* Trade Log (sample) */}
          {result.trade_log.length > 0 && (
            <View style={styles.section}>
              <Text style={styles.sectionTitle}>
                Trade Log (5 terakhir dari {result.trade_log.length})
              </Text>
              {result.trade_log.slice(-5).map(trade => (
                <View key={trade.trade_num} style={styles.tradeRow}>
                  <Text style={styles.tradeNum}>#{trade.trade_num}</Text>
                  <View style={{flex: 1, marginLeft: 8}}>
                    <Text style={styles.tradeDate}>
                      {trade.entry_date} → {trade.exit_date}
                    </Text>
                    <Text style={styles.tradeInfo}>
                      {trade.entry_price.toFixed(4)} → {trade.exit_price.toFixed(4)} | {trade.exit_reason}
                    </Text>
                  </View>
                  <Text
                    style={[
                      styles.tradePnl,
                      {color: trade.is_win ? COLORS.success : COLORS.danger},
                    ]}>
                    {trade.pnl_pct > 0 ? '+' : ''}{trade.pnl_pct.toFixed(2)}%
                  </Text>
                </View>
              ))}
            </View>
          )}

          {/* CTA Activate Scanner */}
          {result.is_qualified && (
            <TouchableOpacity
              style={styles.activateBtn}
              onPress={activateScanner}
              disabled={activatingScanner}>
              {activatingScanner ? (
                <ActivityIndicator color="#fff" />
              ) : (
                <Text style={styles.activateBtnText}>Aktifkan Scanner Live</Text>
              )}
            </TouchableOpacity>
          )}

          {!result.is_qualified && (
            <View style={styles.notQualifiedCard}>
              <Text style={styles.notQualifiedTitle}>Strategi Belum Qualified</Text>
              <Text style={styles.notQualifiedText}>
                Score minimum 50/100 diperlukan. Kembali ke AI Builder untuk menyempurnakan strategi.
              </Text>
            </View>
          )}

          <TouchableOpacity style={styles.rerunBtn} onPress={runBacktest}>
            <Text style={styles.rerunBtnText}>Jalankan Ulang Backtest</Text>
          </TouchableOpacity>

          <View style={{height: 40}} />
        </>
      )}
    </ScrollView>
  );
}

function MetricBox({label, value, color}: {label: string; value: string; color: string}) {
  return (
    <View style={styles.metricBox}>
      <Text style={[styles.metricValue, {color}]}>{value}</Text>
      <Text style={styles.metricLabel}>{label}</Text>
    </View>
  );
}

function WFRow({
  label, inSample, outSample, format,
}: {label: string; inSample: number; outSample: number; format: 'pct' | 'num'}) {
  const fmt = (v: number) =>
    format === 'pct' ? `${(v * 100).toFixed(1)}%` : v.toFixed(2);
  return (
    <View style={styles.wfRow}>
      <Text style={styles.wfLabel}>{label}</Text>
      <Text style={styles.wfVal}>{fmt(inSample)}</Text>
      <Text style={[styles.wfVal, {color: outSample >= inSample * 0.7 ? COLORS.success : COLORS.danger}]}>
        {fmt(outSample)}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {flex: 1, backgroundColor: COLORS.bg},
  infoCard: {
    margin: 12,
    backgroundColor: COLORS.surface,
    borderRadius: 10,
    padding: 14,
    borderWidth: 1,
    borderColor: COLORS.border,
  },
  strategyName: {color: COLORS.text, fontSize: 18, fontWeight: '700'},
  strategyMeta: {color: COLORS.textMuted, fontSize: 13, marginTop: 4},
  runBtn: {
    margin: 12,
    backgroundColor: COLORS.primary,
    borderRadius: 10,
    paddingVertical: 14,
    alignItems: 'center',
  },
  runBtnText: {color: '#fff', fontWeight: '700', fontSize: 16},
  progressCard: {
    margin: 12,
    backgroundColor: COLORS.surface,
    borderRadius: 10,
    padding: 20,
    alignItems: 'center',
    borderWidth: 1,
    borderColor: COLORS.border,
  },
  progressText: {color: COLORS.textMuted, fontSize: 13, marginTop: 12, textAlign: 'center'},
  progressBar: {
    width: '100%', height: 4, backgroundColor: COLORS.border, borderRadius: 2, marginTop: 12,
  },
  progressFill: {height: 4, backgroundColor: COLORS.primary, borderRadius: 2},
  progressPct: {color: COLORS.primary, marginTop: 6, fontWeight: '700'},
  scoreHeader: {margin: 12, alignItems: 'center'},
  scoreBadge: {
    borderRadius: 12,
    padding: 16,
    alignItems: 'center',
    borderWidth: 2,
    minWidth: 160,
  },
  scoreNum: {fontSize: 36, fontWeight: '800'},
  scoreLabel: {fontSize: 14, fontWeight: '700', marginTop: 2},
  metricsGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    marginHorizontal: 12,
    gap: 8,
    marginBottom: 12,
  },
  metricBox: {
    flex: 1,
    minWidth: '30%',
    backgroundColor: COLORS.surface,
    borderRadius: 8,
    padding: 12,
    alignItems: 'center',
    borderWidth: 1,
    borderColor: COLORS.border,
  },
  metricValue: {fontSize: 20, fontWeight: '700'},
  metricLabel: {color: COLORS.textMuted, fontSize: 11, marginTop: 3, textAlign: 'center'},
  wlCard: {
    marginHorizontal: 12, marginBottom: 12, backgroundColor: COLORS.surface,
    borderRadius: 10, padding: 14, borderWidth: 1, borderColor: COLORS.border,
  },
  wlRow: {flexDirection: 'row', justifyContent: 'space-around', marginTop: 8},
  wlItem: {alignItems: 'center'},
  wlNum: {fontSize: 24, fontWeight: '800'},
  wlLabel: {color: COLORS.textMuted, fontSize: 11},
  wlDivider: {width: 1, backgroundColor: COLORS.border},
  wfCard: {
    marginHorizontal: 12, marginBottom: 12, backgroundColor: COLORS.surface,
    borderRadius: 10, padding: 14, borderWidth: 1, borderColor: COLORS.border,
  },
  wfPeriod: {color: COLORS.textMuted, fontSize: 11, marginBottom: 8},
  wfRow: {flexDirection: 'row', justifyContent: 'space-between', paddingVertical: 4},
  wfLabel: {color: COLORS.textMuted, fontSize: 13, flex: 1},
  wfVal: {color: COLORS.text, fontWeight: '600', fontSize: 13, marginLeft: 8},
  degradRow: {flexDirection: 'row', justifyContent: 'space-between', paddingTop: 8, borderTopWidth: 1, borderTopColor: COLORS.border, marginTop: 4},
  section: {
    marginHorizontal: 12, marginBottom: 12,
  },
  sectionTitle: {color: COLORS.text, fontWeight: '700', fontSize: 14, marginBottom: 8},
  tradeRow: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: COLORS.surface,
    borderRadius: 6,
    padding: 8,
    marginBottom: 4,
    borderWidth: 1,
    borderColor: COLORS.border,
  },
  tradeNum: {color: COLORS.textMuted, fontSize: 11, width: 28},
  tradeDate: {color: COLORS.textMuted, fontSize: 10},
  tradeInfo: {color: COLORS.text, fontSize: 12},
  tradePnl: {fontWeight: '700', fontSize: 13},
  activateBtn: {
    margin: 12,
    backgroundColor: COLORS.success,
    borderRadius: 10,
    paddingVertical: 14,
    alignItems: 'center',
  },
  activateBtnText: {color: '#fff', fontWeight: '700', fontSize: 16},
  notQualifiedCard: {
    margin: 12,
    backgroundColor: '#2D1319',
    borderRadius: 10,
    padding: 14,
    borderWidth: 1,
    borderColor: COLORS.danger,
  },
  notQualifiedTitle: {color: COLORS.danger, fontWeight: '700', fontSize: 14},
  notQualifiedText: {color: COLORS.textMuted, fontSize: 13, marginTop: 4},
  rerunBtn: {
    marginHorizontal: 12,
    borderWidth: 1,
    borderColor: COLORS.border,
    borderRadius: 10,
    paddingVertical: 12,
    alignItems: 'center',
    marginTop: 8,
  },
  rerunBtnText: {color: COLORS.textMuted, fontWeight: '600'},
});
