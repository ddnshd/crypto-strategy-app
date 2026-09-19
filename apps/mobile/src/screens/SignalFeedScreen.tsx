import React, {useEffect, useState, useRef} from 'react';
import {
  View,
  Text,
  StyleSheet,
  FlatList,
  TouchableOpacity,
  RefreshControl,
  Alert,
  AppState,
} from 'react-native';
import {useStore} from '../store';
import {signalsApi, createSignalWebSocket} from '../api/signals';
import {getDeviceId} from '../api/client';
import {Signal} from '../types';

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

export default function SignalFeedScreen() {
  const {signals, addSignal, loadSignals, signalsLoading, strategies, scanners, loadScanners} = useStore();
  const [refreshing, setRefreshing] = useState(false);
  const [wsConnected, setWsConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    loadSignals();
    loadScanners();
    setupWebSocket();

    const sub = AppState.addEventListener('change', state => {
      if (state === 'active') {
        if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
          setupWebSocket();
        }
      }
    });

    return () => {
      sub.remove();
      wsRef.current?.close();
    };
  }, []);

  const setupWebSocket = async () => {
    const deviceId = await getDeviceId();
    const ws = createSignalWebSocket(
      deviceId,
      signal => {
        addSignal(signal);
        // You could show a local alert or toast here
      },
      () => setWsConnected(true),
    );
    ws.onclose = () => setWsConnected(false);
    wsRef.current = ws;
  };

  const onRefresh = async () => {
    setRefreshing(true);
    await Promise.all([loadSignals(), loadScanners()]);
    setRefreshing(false);
  };

  const activeScanners = scanners.filter(s => s.is_active);

  return (
    <View style={styles.container}>
      {/* Header Status */}
      <View style={styles.statusBar}>
        <View style={[styles.wsIndicator, {backgroundColor: wsConnected ? COLORS.success : COLORS.danger}]} />
        <Text style={styles.statusText}>
          {wsConnected ? 'Live' : 'Offline'} · {activeScanners.length} scanner aktif
        </Text>
        {activeScanners.length === 0 && (
          <Text style={styles.statusHint}>
            Aktifkan scanner di Library → Backtest
          </Text>
        )}
      </View>

      {/* Signal List */}
      <FlatList
        data={signals}
        keyExtractor={s => s.id}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={COLORS.primary} />
        }
        contentContainerStyle={styles.listContent}
        renderItem={({item}) => (
          <SignalCard
            signal={item}
            strategyName={strategies.find(s => s.id === item.strategy_id)?.name}
          />
        )}
        ListEmptyComponent={() => (
          <View style={styles.emptyContainer}>
            <Text style={styles.emptyIcon}>📡</Text>
            <Text style={styles.emptyText}>Belum ada sinyal</Text>
            <Text style={styles.emptySubtext}>
              Scanner akan otomatis memberi tahu kamu saat kondisi entry terpenuhi
            </Text>
          </View>
        )}
      />
    </View>
  );
}

function SignalCard({signal, strategyName}: {signal: Signal; strategyName?: string}) {
  const isLong = signal.direction === 'long';
  const rr =
    signal.take_profit && signal.stop_loss
      ? Math.abs(signal.take_profit - signal.entry_price) /
        Math.abs(signal.entry_price - signal.stop_loss)
      : null;

  return (
    <View style={styles.signalCard}>
      {/* Top row */}
      <View style={styles.signalTop}>
        <View style={[styles.directionBadge, {backgroundColor: isLong ? '#1B4332' : '#4C0519'}]}>
          <Text style={[styles.directionText, {color: isLong ? COLORS.success : COLORS.danger}]}>
            {signal.direction.toUpperCase()}
          </Text>
        </View>
        <Text style={styles.signalPair}>{signal.pair}</Text>
        <View style={{flex: 1}} />
        {signal.is_hit !== null && signal.is_hit !== undefined ? (
          <View style={[styles.resultBadge, {
            backgroundColor: signal.is_hit ? '#1B4332' : '#4C0519',
            borderColor: signal.is_hit ? COLORS.success : COLORS.danger,
          }]}>
            <Text style={{color: signal.is_hit ? COLORS.success : COLORS.danger, fontSize: 11, fontWeight: '800'}}>
              {signal.is_hit ? `TP +${signal.pnl_pct?.toFixed(2)}%` : `SL ${signal.pnl_pct?.toFixed(2)}%`}
            </Text>
          </View>
        ) : (
          <View style={styles.pendingBadge}>
            <Text style={styles.pendingText}>PENDING</Text>
          </View>
        )}
      </View>

      {/* Strategy name */}
      {strategyName && (
        <Text style={styles.strategyTag}>Strategy: {strategyName}</Text>
      )}

      {/* Price info */}
      <View style={styles.priceRow}>
        <PriceItem label="Entry" value={signal.entry_price.toFixed(6)} color={COLORS.text} />
        {signal.take_profit && (
          <PriceItem label="TP" value={signal.take_profit.toFixed(6)} color={COLORS.success} />
        )}
        {signal.stop_loss && (
          <PriceItem label="SL" value={signal.stop_loss.toFixed(6)} color={COLORS.danger} />
        )}
        {rr && (
          <PriceItem label="R:R" value={`1:${rr.toFixed(1)}`} color={COLORS.warning} />
        )}
      </View>

      {/* Reason */}
      {signal.reason && (
        <Text style={styles.reason} numberOfLines={2}>
          Trigger: {signal.reason}
        </Text>
      )}

      {/* Time */}
      <Text style={styles.signalTime}>
        {new Date(signal.triggered_at).toLocaleString('id-ID', {
          day: '2-digit', month: 'short', year: 'numeric',
          hour: '2-digit', minute: '2-digit',
        })}
      </Text>
    </View>
  );
}

function PriceItem({label, value, color}: {label: string; value: string; color: string}) {
  return (
    <View style={styles.priceItem}>
      <Text style={styles.priceLabel}>{label}</Text>
      <Text style={[styles.priceValue, {color}]}>{value}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {flex: 1, backgroundColor: COLORS.bg},
  statusBar: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: 10,
    paddingHorizontal: 14,
    backgroundColor: COLORS.surface,
    borderBottomWidth: 1,
    borderBottomColor: COLORS.border,
    gap: 8,
  },
  wsIndicator: {width: 8, height: 8, borderRadius: 4},
  statusText: {color: COLORS.text, fontSize: 13, fontWeight: '600'},
  statusHint: {color: COLORS.textMuted, fontSize: 11, marginLeft: 4},
  listContent: {padding: 12},
  signalCard: {
    backgroundColor: COLORS.surface,
    borderRadius: 12,
    padding: 14,
    marginBottom: 10,
    borderWidth: 1,
    borderColor: COLORS.border,
  },
  signalTop: {flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 6},
  directionBadge: {paddingHorizontal: 8, paddingVertical: 3, borderRadius: 5},
  directionText: {fontWeight: '800', fontSize: 12},
  signalPair: {color: COLORS.text, fontWeight: '700', fontSize: 16},
  resultBadge: {
    paddingHorizontal: 8, paddingVertical: 3, borderRadius: 5, borderWidth: 1,
  },
  pendingBadge: {
    paddingHorizontal: 8, paddingVertical: 3, borderRadius: 5,
    backgroundColor: '#21262D', borderWidth: 1, borderColor: COLORS.border,
  },
  pendingText: {color: COLORS.textMuted, fontSize: 11, fontWeight: '700'},
  strategyTag: {color: COLORS.primary, fontSize: 11, marginBottom: 8},
  priceRow: {flexDirection: 'row', gap: 12, marginBottom: 8},
  priceItem: {},
  priceLabel: {color: COLORS.textMuted, fontSize: 10},
  priceValue: {fontWeight: '700', fontSize: 14},
  reason: {color: COLORS.textMuted, fontSize: 11, marginBottom: 6, fontStyle: 'italic'},
  signalTime: {color: COLORS.textMuted, fontSize: 11},
  emptyContainer: {alignItems: 'center', paddingTop: 80},
  emptyIcon: {fontSize: 48, marginBottom: 12},
  emptyText: {color: COLORS.textMuted, fontSize: 18, fontWeight: '700'},
  emptySubtext: {
    color: COLORS.textMuted, fontSize: 13, marginTop: 8,
    textAlign: 'center', paddingHorizontal: 40,
  },
});
