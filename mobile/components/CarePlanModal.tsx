import { useEffect, useState } from 'react';
import {
  ActivityIndicator,
  Modal,
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from 'react-native';
import { apiFetch } from '../lib/api';

type CareEvent = { date: string; day: number; title: string; note: string };
type Care = {
  task: { id: number; display: string; batch_size: number; status: string };
  sown_on: string;
  zone: string;
  past: CareEvent[];
  upcoming: CareEvent[];
};

// Per-planting care schedule (mirrors the web /planner/care page): upcoming steps,
// a "water now" shortcut for the planting's zone, and collapsed earlier steps.
export default function CarePlanModal({
  taskId,
  onClose,
}: {
  taskId: number | null;
  onClose: () => void;
}) {
  const [care, setCare] = useState<Care | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showPast, setShowPast] = useState(false);
  const [watering, setWatering] = useState(false);
  const [waterMsg, setWaterMsg] = useState<string | null>(null);

  useEffect(() => {
    if (taskId == null) return;
    setCare(null);
    setError(null);
    setShowPast(false);
    setWaterMsg(null);
    setLoading(true);
    apiFetch<Care>(`/api/care/${taskId}`)
      .then(setCare)
      .catch((e) => setError(e?.message ?? 'Could not load care plan.'))
      .finally(() => setLoading(false));
  }, [taskId]);

  async function waterNow() {
    if (!care) return;
    setWatering(true);
    setWaterMsg(null);
    try {
      const res = await apiFetch<{ state: string }>('/api/check', {
        method: 'POST',
        body: JSON.stringify({ zone: care.zone }),
      });
      setWaterMsg(`Watering check: ${res.state.toLowerCase()}`);
    } catch (e: any) {
      setWaterMsg(e?.message ?? 'Could not run check.');
    } finally {
      setWatering(false);
    }
  }

  return (
    <Modal visible={taskId != null} animationType="slide" transparent onRequestClose={onClose}>
      <View style={styles.backdrop}>
        <View style={styles.sheet}>
          <ScrollView contentContainerStyle={styles.body}>
            {loading ? (
              <ActivityIndicator color="#3a7d44" style={{ marginVertical: 30 }} />
            ) : error ? (
              <Text style={styles.error}>⚠️  {error}</Text>
            ) : care ? (
              <>
                <Text style={styles.title}>🌿 {care.task.display}</Text>
                <Text style={styles.sub}>
                  {care.task.batch_size} plants · sown {care.sown_on} · zone{' '}
                  <Text style={styles.bold}>{care.zone}</Text>
                </Text>

                <TouchableOpacity style={styles.waterBtn} onPress={waterNow} disabled={watering}>
                  <Text style={styles.waterText}>
                    {watering ? 'Checking…' : '💧 Watering check'}
                  </Text>
                </TouchableOpacity>
                {waterMsg ? <Text style={styles.waterMsg}>{waterMsg}</Text> : null}

                <Text style={styles.section}>📌 Up next</Text>
                {care.upcoming.length === 0 ? (
                  <Text style={styles.empty}>
                    No more scheduled care — this planting should be wrapping up.
                  </Text>
                ) : (
                  care.upcoming.map((e, i) => (
                    <View key={`u${i}`} style={[styles.event, i === 0 && styles.eventNext]}>
                      <Text style={styles.eventTop}>
                        <Text style={styles.eventDate}>{e.date}</Text> · {e.title}
                        {i === 0 ? '  ⭐' : ''}
                      </Text>
                      <Text style={styles.eventNote}>{e.note}</Text>
                    </View>
                  ))
                )}

                {care.past.length > 0 ? (
                  <>
                    <TouchableOpacity onPress={() => setShowPast((v) => !v)}>
                      <Text style={styles.toggle}>
                        {showPast ? '▾' : '▸'} Earlier steps ({care.past.length})
                      </Text>
                    </TouchableOpacity>
                    {showPast
                      ? care.past.map((e, i) => (
                          <View key={`p${i}`} style={[styles.event, styles.eventPast]}>
                            <Text style={styles.eventTop}>
                              <Text style={styles.eventDate}>{e.date}</Text> · {e.title}
                            </Text>
                            <Text style={styles.eventNote}>{e.note}</Text>
                          </View>
                        ))
                      : null}
                  </>
                ) : null}
              </>
            ) : null}
          </ScrollView>
          <TouchableOpacity onPress={onClose} style={styles.closeBtn}>
            <Text style={styles.close}>Close</Text>
          </TouchableOpacity>
        </View>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  backdrop: { flex: 1, backgroundColor: 'rgba(0,0,0,0.35)', justifyContent: 'flex-end' },
  sheet: {
    backgroundColor: '#fcfcfa', borderTopLeftRadius: 18, borderTopRightRadius: 18,
    maxHeight: '88%',
  },
  body: { padding: 22, paddingBottom: 10 },
  title: { fontSize: 22, fontWeight: '800', color: '#222' },
  sub: { color: '#777', fontSize: 13, marginTop: 4 },
  bold: { fontWeight: '700', color: '#3a7d44' },
  waterBtn: {
    marginTop: 14, backgroundColor: '#eaf2fb', borderWidth: 1, borderColor: '#cfe0f2',
    borderRadius: 10, paddingVertical: 12, alignItems: 'center',
  },
  waterText: { color: '#1a6faf', fontWeight: '700', fontSize: 15 },
  waterMsg: { color: '#2f6b3a', fontSize: 13, marginTop: 8, textAlign: 'center' },
  section: { fontSize: 15, fontWeight: '800', color: '#444', marginTop: 22, marginBottom: 8 },
  empty: { color: '#999', lineHeight: 20 },
  event: {
    backgroundColor: '#fff', borderRadius: 10, padding: 12, marginBottom: 8,
    borderWidth: 1, borderColor: '#ececec',
  },
  eventNext: { borderColor: '#e0b878', backgroundColor: '#fffaf2' },
  eventPast: { opacity: 0.65 },
  eventTop: { fontSize: 14, color: '#222', fontWeight: '600' },
  eventDate: { color: '#3a7d44', fontWeight: '700' },
  eventNote: { fontSize: 13, color: '#666', marginTop: 4, lineHeight: 19 },
  toggle: { color: '#1a6faf', fontWeight: '700', marginTop: 14, marginBottom: 6, fontSize: 14 },
  error: { color: '#c0392b', fontSize: 14, marginVertical: 20 },
  closeBtn: { padding: 16, borderTopWidth: 1, borderTopColor: '#eee' },
  close: { textAlign: 'center', color: '#888', fontSize: 15 },
});
