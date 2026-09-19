import React, {useEffect, useState} from 'react';
import {
  View,
  Text,
  StyleSheet,
  FlatList,
  TouchableOpacity,
  Alert,
  RefreshControl,
  TextInput,
} from 'react-native';
import {useNavigation} from '@react-navigation/native';
import {useStore} from '../store';
import {strategiesApi} from '../api/strategies';
import {Strategy} from '../types';

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

const STYLE_COLORS: Record<string, string> = {
  scalp: '#D29922',
  intraday: '#58A6FF',
  swing: '#3FB950',
  position: '#BC8CFF',
};

export default function StrategyLibraryScreen() {
  const navigation = useNavigation<any>();
  const {strategies, loadStrategies, removeStrategy, strategiesLoading} = useStore();
  const [refreshing, setRefreshing] = useState(false);
  const [search, setSearch] = useState('');
  const [filterStyle, setFilterStyle] = useState<string | null>(null);

  useEffect(() => {
    loadStrategies();
  }, []);

  const onRefresh = async () => {
    setRefreshing(true);
    await loadStrategies();
    setRefreshing(false);
  };

  const handleDelete = (strategy: Strategy) => {
    Alert.alert(
      'Hapus Strategi',
      `Hapus "${strategy.name}"? Semua hasil backtest dan sinyal terkait juga akan dihapus.`,
      [
        {text: 'Batal', style: 'cancel'},
        {
          text: 'Hapus',
          style: 'destructive',
          onPress: async () => {
            try {
              await strategiesApi.delete(strategy.id);
              removeStrategy(strategy.id);
            } catch (e: any) {
              Alert.alert('Error', e.message);
            }
          },
        },
      ],
    );
  };

  const handleDuplicate = async (strategy: Strategy) => {
    try {
      const duped = await strategiesApi.duplicate(strategy.id);
      useStore.getState().addStrategy(duped);
      Alert.alert('Berhasil', `"${duped.name}" berhasil diduplikasi`);
    } catch (e: any) {
      Alert.alert('Error', e.message);
    }
  };

  const filteredStrategies = strategies.filter(s => {
    const matchSearch =
      !search ||
      s.name.toLowerCase().includes(search.toLowerCase()) ||
      s.pair.toLowerCase().includes(search.toLowerCase());
    const matchStyle = !filterStyle || s.style === filterStyle;
    return matchSearch && matchStyle;
  });

  return (
    <View style={styles.container}>
      {/* Search */}
      <View style={styles.searchRow}>
        <TextInput
          style={styles.searchInput}
          value={search}
          onChangeText={setSearch}
          placeholder="Cari strategi atau pair..."
          placeholderTextColor={COLORS.textMuted}
        />
      </View>

      {/* Style Filter */}
      <View style={styles.filterRow}>
        {[null, 'scalp', 'intraday', 'swing', 'position'].map(style => (
          <TouchableOpacity
            key={style ?? 'all'}
            style={[
              styles.filterChip,
              filterStyle === style && {backgroundColor: COLORS.primary},
            ]}
            onPress={() => setFilterStyle(style)}>
            <Text
              style={[
                styles.filterChipText,
                filterStyle === style && {color: '#fff'},
              ]}>
              {style ? style.charAt(0).toUpperCase() + style.slice(1) : 'Semua'}
            </Text>
          </TouchableOpacity>
        ))}
      </View>

      {/* List */}
      <FlatList
        data={filteredStrategies}
        keyExtractor={s => s.id}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={COLORS.primary} />}
        contentContainerStyle={styles.listContent}
        renderItem={({item}) => (
          <StrategyCard
            strategy={item}
            onPress={() => navigation.navigate('StrategyDetail', {strategyId: item.id})}
            onBacktest={() => navigation.navigate('Backtest', {strategyId: item.id})}
            onDelete={() => handleDelete(item)}
            onDuplicate={() => handleDuplicate(item)}
          />
        )}
        ListEmptyComponent={() => (
          <View style={styles.emptyContainer}>
            <Text style={styles.emptyText}>Belum ada strategi</Text>
            <Text style={styles.emptySubtext}>
              Buat strategi baru di tab AI Builder
            </Text>
          </View>
        )}
      />
    </View>
  );
}

function StrategyCard({
  strategy,
  onPress,
  onBacktest,
  onDelete,
  onDuplicate,
}: {
  strategy: Strategy;
  onPress: () => void;
  onBacktest: () => void;
  onDelete: () => void;
  onDuplicate: () => void;
}) {
  const styleColor = STYLE_COLORS[strategy.style] ?? COLORS.textMuted;
  const scoreColor =
    (strategy.backtest_score ?? 0) >= 70
      ? COLORS.success
      : (strategy.backtest_score ?? 0) >= 50
      ? COLORS.warning
      : COLORS.danger;

  return (
    <TouchableOpacity style={styles.card} onPress={onPress} activeOpacity={0.8}>
      {/* Header */}
      <View style={styles.cardHeader}>
        <View style={{flex: 1}}>
          <View style={styles.cardTitleRow}>
            <View style={[styles.styleBadge, {backgroundColor: styleColor + '22', borderColor: styleColor}]}>
              <Text style={[styles.styleBadgeText, {color: styleColor}]}>
                {strategy.style.toUpperCase()}
              </Text>
            </View>
            {strategy.is_active && (
              <View style={styles.activePip}>
                <Text style={styles.activePipText}>LIVE</Text>
              </View>
            )}
          </View>
          <Text style={styles.cardName} numberOfLines={1}>{strategy.name}</Text>
          <Text style={styles.cardMeta}>
            {strategy.pair} · {strategy.timeframe}
          </Text>
        </View>

        {strategy.backtest_score !== null && strategy.backtest_score !== undefined && (
          <View style={styles.scoreBox}>
            <Text style={[styles.scoreValue, {color: scoreColor}]}>
              {strategy.backtest_score.toFixed(0)}
            </Text>
            <Text style={styles.scoreLabel}>/ 100</Text>
          </View>
        )}
      </View>

      {/* Status */}
      <View style={styles.cardStatus}>
        <StatusDot
          active={strategy.is_backtested}
          label={strategy.is_backtested ? 'Sudah backtest' : 'Belum backtest'}
        />
      </View>

      {/* Actions */}
      <View style={styles.cardActions}>
        <TouchableOpacity style={styles.actionBtn} onPress={onBacktest}>
          <Text style={styles.actionBtnText}>Backtest</Text>
        </TouchableOpacity>
        <TouchableOpacity style={styles.actionBtn} onPress={onDuplicate}>
          <Text style={styles.actionBtnText}>Duplikat</Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={[styles.actionBtn, {borderColor: COLORS.danger}]}
          onPress={onDelete}>
          <Text style={[styles.actionBtnText, {color: COLORS.danger}]}>Hapus</Text>
        </TouchableOpacity>
      </View>
    </TouchableOpacity>
  );
}

function StatusDot({active, label}: {active: boolean; label: string}) {
  return (
    <View style={{flexDirection: 'row', alignItems: 'center', gap: 5}}>
      <View style={{
        width: 6, height: 6, borderRadius: 3,
        backgroundColor: active ? COLORS.success : COLORS.textMuted,
      }} />
      <Text style={{color: active ? COLORS.success : COLORS.textMuted, fontSize: 12}}>
        {label}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {flex: 1, backgroundColor: COLORS.bg},
  searchRow: {padding: 12, paddingBottom: 6},
  searchInput: {
    backgroundColor: COLORS.surface,
    color: COLORS.text,
    borderRadius: 10,
    paddingHorizontal: 14,
    paddingVertical: 10,
    fontSize: 14,
    borderWidth: 1,
    borderColor: COLORS.border,
  },
  filterRow: {flexDirection: 'row', paddingHorizontal: 12, gap: 8, marginBottom: 6},
  filterChip: {
    paddingHorizontal: 10,
    paddingVertical: 5,
    borderRadius: 20,
    backgroundColor: COLORS.surface,
    borderWidth: 1,
    borderColor: COLORS.border,
  },
  filterChipText: {color: COLORS.textMuted, fontSize: 12, fontWeight: '600'},
  listContent: {padding: 12, paddingTop: 6},
  card: {
    backgroundColor: COLORS.surface,
    borderRadius: 12,
    padding: 14,
    marginBottom: 10,
    borderWidth: 1,
    borderColor: COLORS.border,
  },
  cardHeader: {flexDirection: 'row', alignItems: 'flex-start'},
  cardTitleRow: {flexDirection: 'row', gap: 6, marginBottom: 4},
  styleBadge: {
    paddingHorizontal: 6, paddingVertical: 2, borderRadius: 4, borderWidth: 1,
  },
  styleBadgeText: {fontSize: 10, fontWeight: '800'},
  activePip: {backgroundColor: '#1B4332', paddingHorizontal: 6, paddingVertical: 2, borderRadius: 4},
  activePipText: {color: COLORS.success, fontSize: 10, fontWeight: '800'},
  cardName: {color: COLORS.text, fontSize: 15, fontWeight: '700'},
  cardMeta: {color: COLORS.textMuted, fontSize: 12, marginTop: 2},
  scoreBox: {alignItems: 'center', marginLeft: 10},
  scoreValue: {fontSize: 24, fontWeight: '800'},
  scoreLabel: {color: COLORS.textMuted, fontSize: 11},
  cardStatus: {marginTop: 8, marginBottom: 8},
  cardActions: {flexDirection: 'row', gap: 8, borderTopWidth: 1, borderTopColor: COLORS.border, paddingTop: 10},
  actionBtn: {
    flex: 1,
    borderRadius: 6,
    paddingVertical: 6,
    alignItems: 'center',
    borderWidth: 1,
    borderColor: COLORS.border,
  },
  actionBtnText: {color: COLORS.text, fontSize: 12, fontWeight: '600'},
  emptyContainer: {alignItems: 'center', paddingTop: 60},
  emptyText: {color: COLORS.textMuted, fontSize: 16, fontWeight: '600'},
  emptySubtext: {color: COLORS.textMuted, fontSize: 13, marginTop: 6},
});
