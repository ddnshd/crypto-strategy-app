import React, {useState, useRef, useCallback} from 'react';
import {
  View,
  Text,
  StyleSheet,
  TextInput,
  TouchableOpacity,
  FlatList,
  KeyboardAvoidingView,
  Platform,
  ActivityIndicator,
  Alert,
  ScrollView,
} from 'react-native';
import {strategiesApi} from '../api/strategies';
import {useStore} from '../store';
import {ChatMessage, AIStrategyResponse, StrategyDefinition} from '../types';

const COLORS = {
  bg: '#0D1117',
  surface: '#161B22',
  surfaceAlt: '#21262D',
  border: '#30363D',
  primary: '#58A6FF',
  success: '#3FB950',
  danger: '#F85149',
  warning: '#D29922',
  text: '#E6EDF3',
  textMuted: '#8B949E',
};

type BuilderStep = 'chat' | 'preview' | 'saving';

export default function StrategyBuilderScreen() {
  const {addStrategy} = useStore();
  const [step, setStep] = useState<BuilderStep>('chat');
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      role: 'assistant',
      content:
        'Halo! Saya AI Strategy Builder. Ceritakan ide strategi trading kamu dalam bahasa natural.\n\nContoh:\n"Beli BTC saat RSI di bawah 30 dan harga cross di atas EMA 50, TP 2%, SL 1%, timeframe 15 menit"\n\nAtau kamu bisa tanya dulu soal indikator atau strategi tertentu.',
    },
  ]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [generatedStrategy, setGeneratedStrategy] = useState<AIStrategyResponse | null>(null);
  const [strategyName, setStrategyName] = useState('');
  const [isSaving, setIsSaving] = useState(false);
  const flatListRef = useRef<FlatList>(null);

  const sendMessage = useCallback(async () => {
    if (!input.trim() || isLoading) return;

    const userMsg: ChatMessage = {role: 'user', content: input.trim()};
    const newMessages = [...messages, userMsg];
    setMessages(newMessages);
    setInput('');
    setIsLoading(true);

    try {
      // Detect if user wants to CREATE a strategy (vs just chat)
      const wantsStrategy =
        input.toLowerCase().includes('beli') ||
        input.toLowerCase().includes('jual') ||
        input.toLowerCase().includes('strategi') ||
        input.toLowerCase().includes('entry') ||
        input.toLowerCase().includes('tp') ||
        input.toLowerCase().includes('sl') ||
        input.toLowerCase().includes('rsi') ||
        input.toLowerCase().includes('ema') ||
        input.toLowerCase().includes('macd');

      if (wantsStrategy) {
        const result = await strategiesApi.generateStrategy(input.trim());
        setGeneratedStrategy(result);

        const aiMsg: ChatMessage = {
          role: 'assistant',
          content: `Strategi berhasil dibuat!\n\n${result.explanation}\n\n${
            result.suggestions.length > 0
              ? `**Saran:**\n${result.suggestions.map(s => `• ${s}`).join('\n')}`
              : ''
          }${
            result.warnings.length > 0
              ? `\n\n**Peringatan:**\n${result.warnings.map(w => `⚠️ ${w}`).join('\n')}`
              : ''
          }\n\nScroll ke bawah untuk preview dan simpan strategi.`,
        };
        setMessages([...newMessages, aiMsg]);
        setStrategyName(result.strategy.name);
        setTimeout(() => setStep('preview'), 300);
      } else {
        // General chat
        const reply = await strategiesApi.chat(
          newMessages.map(m => ({role: m.role, content: m.content})),
        );
        setMessages([...newMessages, {role: 'assistant', content: reply}]);
      }
    } catch (err: any) {
      setMessages([
        ...newMessages,
        {role: 'assistant', content: `Maaf, terjadi kesalahan: ${err.message}`},
      ]);
    } finally {
      setIsLoading(false);
      setTimeout(() => flatListRef.current?.scrollToEnd({animated: true}), 200);
    }
  }, [input, messages, isLoading]);

  const saveStrategy = async () => {
    if (!generatedStrategy) return;
    setIsSaving(true);
    try {
      const saved = await strategiesApi.create({
        name: strategyName || generatedStrategy.strategy.name,
        description: generatedStrategy.explanation.slice(0, 300),
        style: generatedStrategy.strategy.style,
        pair: generatedStrategy.strategy.pair,
        timeframe: generatedStrategy.strategy.timeframe,
        definition: generatedStrategy.strategy as any,
        device_id: '', // will be set by api client
      });
      addStrategy(saved);
      Alert.alert(
        'Strategi Tersimpan',
        `"${saved.name}" berhasil disimpan. Sekarang lakukan backtest di halaman Library.`,
        [{text: 'OK', onPress: () => resetBuilder()}],
      );
    } catch (err: any) {
      Alert.alert('Gagal', err.message);
    } finally {
      setIsSaving(false);
    }
  };

  const resetBuilder = () => {
    setStep('chat');
    setGeneratedStrategy(null);
    setStrategyName('');
    setMessages([
      {
        role: 'assistant',
        content: 'Strategi tersimpan! Mau buat strategi lain? Ceritakan ide kamu.',
      },
    ]);
  };

  return (
    <KeyboardAvoidingView
      style={styles.container}
      behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
      keyboardVerticalOffset={90}>
      {/* Chat Messages */}
      <FlatList
        ref={flatListRef}
        data={messages}
        keyExtractor={(_, i) => i.toString()}
        renderItem={({item}) => <ChatBubble message={item} />}
        contentContainerStyle={styles.chatContainer}
        onContentSizeChange={() => flatListRef.current?.scrollToEnd()}
        style={{flex: 1}}
      />

      {/* Loading indicator */}
      {isLoading && (
        <View style={styles.thinkingRow}>
          <ActivityIndicator color={COLORS.primary} size="small" />
          <Text style={styles.thinkingText}>AI sedang memproses...</Text>
        </View>
      )}

      {/* Strategy Preview */}
      {step === 'preview' && generatedStrategy && (
        <View style={styles.previewPanel}>
          <Text style={styles.previewTitle}>Preview Strategi</Text>
          <ScrollView style={{maxHeight: 200}} showsVerticalScrollIndicator>
            <StrategyPreview strategy={generatedStrategy.strategy} />
          </ScrollView>
          <TextInput
            style={styles.nameInput}
            value={strategyName}
            onChangeText={setStrategyName}
            placeholder="Nama strategi..."
            placeholderTextColor={COLORS.textMuted}
          />
          <View style={styles.previewActions}>
            <TouchableOpacity
              style={[styles.btn, styles.btnOutline]}
              onPress={() => setStep('chat')}>
              <Text style={styles.btnOutlineText}>Edit lagi</Text>
            </TouchableOpacity>
            <TouchableOpacity
              style={[styles.btn, styles.btnPrimary]}
              onPress={saveStrategy}
              disabled={isSaving}>
              {isSaving ? (
                <ActivityIndicator color="#fff" size="small" />
              ) : (
                <Text style={styles.btnPrimaryText}>Simpan Strategi</Text>
              )}
            </TouchableOpacity>
          </View>
        </View>
      )}

      {/* Input Bar */}
      {step === 'chat' && (
        <View style={styles.inputBar}>
          <TextInput
            style={styles.input}
            value={input}
            onChangeText={setInput}
            placeholder="Ceritakan ide strategi..."
            placeholderTextColor={COLORS.textMuted}
            multiline
            maxLength={500}
            returnKeyType="send"
            onSubmitEditing={sendMessage}
          />
          <TouchableOpacity
            style={[styles.sendBtn, (!input.trim() || isLoading) && styles.sendBtnDisabled]}
            onPress={sendMessage}
            disabled={!input.trim() || isLoading}>
            <Text style={styles.sendBtnText}>Kirim</Text>
          </TouchableOpacity>
        </View>
      )}
    </KeyboardAvoidingView>
  );
}

function ChatBubble({message}: {message: ChatMessage}) {
  const isUser = message.role === 'user';
  return (
    <View style={[styles.bubble, isUser ? styles.bubbleUser : styles.bubbleAI]}>
      <Text style={[styles.bubbleText, isUser ? styles.bubbleTextUser : styles.bubbleTextAI]}>
        {message.content}
      </Text>
    </View>
  );
}

function StrategyPreview({strategy}: {strategy: StrategyDefinition}) {
  return (
    <View>
      <Text style={styles.previewMeta}>
        {strategy.style.toUpperCase()} | {strategy.pair} | {strategy.timeframe}
      </Text>
      <Text style={styles.previewSubtitle}>Entry Conditions:</Text>
      {strategy.entry_conditions.map((cond, i) => (
        <Text key={i} style={styles.previewCond}>
          • {cond.indicator} {cond.operator} {cond.value ?? ''}
          {Object.keys(cond.params).length > 0
            ? ` (${Object.entries(cond.params)
                .map(([k, v]) => `${k}:${v}`)
                .join(', ')})`
            : ''}
        </Text>
      ))}
      <Text style={styles.previewSubtitle}>Exit:</Text>
      {strategy.exit_conditions.take_profit_pct && (
        <Text style={styles.previewCond}>• TP: {strategy.exit_conditions.take_profit_pct}%</Text>
      )}
      {strategy.exit_conditions.stop_loss_pct && (
        <Text style={styles.previewCond}>• SL: {strategy.exit_conditions.stop_loss_pct}%</Text>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {flex: 1, backgroundColor: COLORS.bg},
  chatContainer: {padding: 12, paddingBottom: 4},
  bubble: {maxWidth: '85%', borderRadius: 14, padding: 12, marginBottom: 8},
  bubbleUser: {backgroundColor: '#1F4E8A', alignSelf: 'flex-end'},
  bubbleAI: {backgroundColor: COLORS.surface, alignSelf: 'flex-start', borderWidth: 1, borderColor: COLORS.border},
  bubbleText: {fontSize: 14, lineHeight: 20},
  bubbleTextUser: {color: '#fff'},
  bubbleTextAI: {color: COLORS.text},
  thinkingRow: {flexDirection: 'row', alignItems: 'center', padding: 10, gap: 8},
  thinkingText: {color: COLORS.textMuted, fontSize: 13},
  inputBar: {
    flexDirection: 'row',
    padding: 10,
    borderTopWidth: 1,
    borderTopColor: COLORS.border,
    alignItems: 'flex-end',
    gap: 8,
  },
  input: {
    flex: 1,
    backgroundColor: COLORS.surfaceAlt,
    color: COLORS.text,
    borderRadius: 12,
    paddingHorizontal: 14,
    paddingVertical: 10,
    maxHeight: 120,
    fontSize: 14,
    borderWidth: 1,
    borderColor: COLORS.border,
  },
  sendBtn: {backgroundColor: COLORS.primary, borderRadius: 10, paddingHorizontal: 14, paddingVertical: 10},
  sendBtnDisabled: {backgroundColor: COLORS.border},
  sendBtnText: {color: '#fff', fontWeight: '700'},
  previewPanel: {
    backgroundColor: COLORS.surface,
    borderTopWidth: 1,
    borderTopColor: COLORS.border,
    padding: 14,
  },
  previewTitle: {color: COLORS.text, fontWeight: '700', fontSize: 15, marginBottom: 8},
  previewMeta: {color: COLORS.primary, fontWeight: '600', fontSize: 13, marginBottom: 6},
  previewSubtitle: {color: COLORS.warning, fontSize: 12, fontWeight: '600', marginTop: 6, marginBottom: 2},
  previewCond: {color: COLORS.text, fontSize: 12, paddingLeft: 4},
  nameInput: {
    backgroundColor: COLORS.surfaceAlt,
    color: COLORS.text,
    borderRadius: 8,
    paddingHorizontal: 12,
    paddingVertical: 8,
    marginTop: 10,
    fontSize: 14,
    borderWidth: 1,
    borderColor: COLORS.border,
  },
  previewActions: {flexDirection: 'row', gap: 8, marginTop: 10},
  btn: {flex: 1, borderRadius: 8, paddingVertical: 10, alignItems: 'center'},
  btnPrimary: {backgroundColor: COLORS.primary},
  btnPrimaryText: {color: '#fff', fontWeight: '700'},
  btnOutline: {borderWidth: 1, borderColor: COLORS.border},
  btnOutlineText: {color: COLORS.text, fontWeight: '600'},
});
