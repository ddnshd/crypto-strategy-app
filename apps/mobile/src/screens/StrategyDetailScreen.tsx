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
import {RouteProp, useRoute, useNavigation} from '@react-navigation/native';
import {useStore} from '../store';
import {strategiesApi} from '../api/strategies';
import {backtestApi} from '../api/backtest';
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

export default function StrategyDetailScreen() {
  const route = useRoute<RouteProp<{StrategyDetail: RouteParams}, 'StrategyDetail'>>();
  const navigation = useNavigation<any>();
  const {strategyId} = route.params;
  const {strategies, updateStrategy} = useStore();

  const strategy = strategies.find(s => s.id === strategyId);
  const [backtests, setBacktests] = useState<BacktestResult[]>([]);
  const [loading, setLoading] = useState(true);
  const [versions, setVersions] = useState<any[]>([]);

  useEffect(() => {
    if (!strategyId) return;
    Promise.all([
      backtestApi.listForStrategy(strategyId),
      strategiesApi.getVersions(strategyId),
    ]).then(([bt, v]) => {
      setBacktests(bt);
      setVersions(v);
    }).catch(console.error)
      .finally(() => setLoading(false));
  }, [strategyId]);

  if (!strategy) {
    return (
      <View style={styles.container}>
        <Text style={{color: COLORS.textMuted, padding: 20}}>Strategi tidak ditemukan</Text>
      </View>
    );
  }

  const def = strategy.definition as any;

  return (
    <ScrollView style={styles.container}>
      {/* Info */}
      <View style={styles.card}>
        <Text style={styles.heading}>{strategy.name}</Text>
        <Text style={styles.meta}>
          {strategy.style.toUpperCase()} · {strategy.pair} · {strategy.timeframe}
        </Text>
        {strategy.description && (
          <Text style={styles.description}>{strategy.description}</Text>
        )}
        {strategy.backtest_score !== null && strategy.backtest_score !== undefined && (
          <View style={styles.scoreRow}>
            <Text style={styles.scoreLabel}>Backtest Score</Text>
            <Text style={[styles.scoreValue, {
              color: strategy.backtest_score >= 70 ? COLORS.success :
                strategy.backtest_score >= 50 ? COLORS.warning : COLORS.danger,
            }]}>
              {strategy.backtest_score.toFixed(0)}/100
            </Text>
          </View>
        )}
      </View>

      {/* Strategy Logic */}
      <View style={styles.card}>
        <Text style={styles.sectionTitle}>Entry Conditions</Text>
        {def?.entry_conditions?.map((cond: any, i: number) => (
          <View key={i} style={styles.condRow}>
            <Text style={styles.condIndicator}>{cond.indicator}</Text>
            <Text style={styles.condOp}>{cond.operator}</Text>
            {cond.value !== undefined && <Text style={styles.condVal}>{cond.value}</Text>}
            {Object.keys(cond.params ?? {}).length > 0 && (
              <Text style={styles.condParams}>
                ({Object.entries(cond.params).map(([k, v]) => `${k}:${v}`).join(', ')})
              </Text>
            )}
          </View>
        ))}

        <Text style={[styles.sectionTitle, {marginTop: 12}]}>Exit Rules</Text>
        {def?.exit_conditions?.take_profit_pct && (
          <View style={styles.condRow}>
            <Text style={styles.condIndicator}>Take Profit</Text>
            <Text style={[styles.condVal, {color: COLORS.success}]}>
              {def.exit_conditions.take_profit_pct}%
            </Text>
          </View>
        )}
        {def?.exit_conditions?.stop_loss_pct && (
          <View style={styles.condRow}>
            <Text style={styles.condIndicator}>Stop Loss</Text>
            <Text style={[styles.condVal, {color: COLORS.danger}]}>
              {def.exit_conditions.stop_loss_pct}%
            </Text>
          </View>
        )}
        {def?.exit_conditions?.trailing_stop_pct && (
          <View style={styles.condRow}>
            <Text style={styles.condIndicator}>Trailing Stop</Text>
            <Text style={[styles.condVal, {color: COLORS.warning}]}>
              {def.exit_conditions.trailing_stop_pct}%
            </Text>
          </View>
        )}

        {def?.filters?.length > 0 && (
          <>
            <Text style={[styles.sectionTitle, {marginTop: 12}]}>Filters</Text>
            {def.filters.map((cond: any, i: number) => (
              <View key={i} style={styles.condRow}>
                <Text style={styles.condIndicator}>{cond.indicator}</Text>
                <Text style={styles.condOp}>{cond.operator}</Text>
                {cond.value !== undefined && <Text style={styles.condVal}>{cond.value}</Text>}
              </View>
            ))}
          </>
        )}
      </View>

      {/* Actions */}
      <View style={styles.actionsRow}>
        <TouchableOpacity
          style={[styles.btn, {backgroundColor: COLORS.primary}]}
          onPress={() => navigation.navigate('Backtest', {strategyId})}>
          <Text style={styles.btnText}>Run Backtest</Text>
        </TouchableOpacity>
      </View>

      {/* Backtest History */}
      {loading ? (
        <ActivityIndicator color={COLORS.primary} style={{margin: 20}} />
      ) : backtests.length > 0 ? (
        <View style={styles.card}>
          <Text style={styles.sectionTitle}>Riwayat Backtest</Text>
          {backtests.map(bt => (
            <View key={bt.id} style={styles.btRow}>
              <View style={{flex: 1}}>
                <Text style={styles.btDate}>
                  {bt.start_date} s/d {bt.end_date}
                </Text>
                <Text style={styles.btMeta}>
                  WR: {(bt.win_rate * 100).toFixed(1)}% · PF: {bt.profit_factor.toFixed(2)} · DD: {(bt.max_drawdown * 100).toFixed(1)}%
                </Text>
              </View>
              <View style={[styles.btScore, {
                backgroundColor: bt.is_qualified ? '#1B4332' : '#4C0519',
              }]}>
                <Text style={{
                  color: bt.is_qualified ? COLORS.success : COLORS.danger,
                  fontWeight: '700', fontSize: 13,
                }}>
                  {bt.score.toFixed(0)}
                </Text>
              </View>
            </View>
          ))}
        </View>
      ) : null}

      {/* Version History */}
      {versions.length > 0 && (
        <View style={styles.card}>
          <Text style={styles.sectionTitle}>Riwayat Versi ({versions.length})</Text>
          {versions.slice(0, 5).map(v => (
            <View key={v.id} style={styles.versionRow}>
              <Text style={styles.versionNum}>v{v.version}</Text>
              <Text style={styles.versionNote}>{v.change_note ?? 'No note'}</Text>
              <Text style={styles.versionDate}>
                {new Date(v.created_at).toLocaleDateString('id-ID')}
              </Text>
            </View>
          ))}
        </View>
      )}

      <View style={{height: 40}} />
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {flex: 1, backgroundColor: COLORS.bg},
  card: {
    margin: 12,
    marginBottom: 0,
    backgroundColor: COLORS.surface,
    borderRadius: 12,
    padding: 14,
    borderWidth: 1,
    borderColor: COLORS.border,
  },
  heading: {color: COLORS.text, fontSize: 20, fontWeight: '700'},
  meta: {color: COLORS.primary, fontSize: 13, marginTop: 4},
  description: {color: COLORS.textMuted, fontSize: 13, marginTop: 6},
  scoreRow: {flexDirection: 'row', justifyContent: 'space-between', marginTop: 10, paddingTop: 10, borderTopWidth: 1, borderTopColor: COLORS.border},
  scoreLabel: {color: COLORS.textMuted, fontSize: 13},
  scoreValue: {fontSize: 18, fontWeight: '700'},
  sectionTitle: {color: COLORS.text, fontWeight: '700', fontSize: 14, marginBottom: 8},
  condRow: {flexDirection: 'row', alignItems: 'center', gap: 6, marginBottom: 5},
  condIndicator: {color: COLORS.primary, fontWeight: '600', fontSize: 13},
  condOp: {color: COLORS.textMuted, fontSize: 13},
  condVal: {color: COLORS.text, fontWeight: '600', fontSize: 13},
  condParams: {color: COLORS.textMuted, fontSize: 11},
  actionsRow: {margin: 12, marginBottom: 0},
  btn: {borderRadius: 10, paddingVertical: 12, alignItems: 'center'},
  btnText: {color: '#fff', fontWeight: '700', fontSize: 15},
  btRow: {
    flexDirection: 'row', alignItems: 'center',
    borderBottomWidth: 1, borderBottomColor: COLORS.border,
    paddingVertical: 8,
  },
  btDate: {color: COLORS.text, fontSize: 13},
  btMeta: {color: COLORS.textMuted, fontSize: 11, marginTop: 2},
  btScore: {borderRadius: 6, paddingHorizontal: 8, paddingVertical: 4},
  versionRow: {
    flexDirection: 'row', alignItems: 'center', gap: 8,
    paddingVertical: 6, borderBottomWidth: 1, borderBottomColor: COLORS.border,
  },
  versionNum: {color: COLORS.primary, fontWeight: '700', width: 32},
  versionNote: {flex: 1, color: COLORS.text, fontSize: 12},
  versionDate: {color: COLORS.textMuted, fontSize: 11},
});
