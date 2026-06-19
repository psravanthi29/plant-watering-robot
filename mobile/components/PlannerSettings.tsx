import { useEffect, useState } from 'react';
import {
  ActivityIndicator,
  Modal,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from 'react-native';
import { apiFetch } from '../lib/api';

type Settings = { household_size: number; plan_start_date: string };

// People-to-feed + plan start date. Changing people-to-feed rescales every crop
// that's on "auto" demand (matches the web planner's Settings tab).
export default function PlannerSettings({
  visible,
  onClose,
  onSaved,
}: {
  visible: boolean;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [household, setHousehold] = useState('');
  const [startDate, setStartDate] = useState('');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!visible) return;
    setLoading(true);
    setError(null);
    apiFetch<Settings>('/api/planner/settings')
      .then((s) => {
        setHousehold(String(s.household_size));
        setStartDate(s.plan_start_date);
      })
      .catch((e) => setError(e?.message ?? 'Could not load settings.'))
      .finally(() => setLoading(false));
  }, [visible]);

  async function save() {
    setSaving(true);
    setError(null);
    try {
      await apiFetch('/api/planner/settings', {
        method: 'POST',
        body: JSON.stringify({
          household_size: household.trim() ? Number(household) : undefined,
          plan_start_date: startDate.trim() || undefined,
        }),
      });
      onSaved();
      onClose();
    } catch (e: any) {
      setError(e?.message ?? 'Could not save.');
    } finally {
      setSaving(false);
    }
  }

  return (
    <Modal visible={visible} animationType="slide" transparent onRequestClose={onClose}>
      <View style={styles.backdrop}>
        <View style={styles.sheet}>
          <Text style={styles.title}>Planner settings</Text>
          {loading ? (
            <ActivityIndicator color="#3a7d44" style={{ marginVertical: 24 }} />
          ) : (
            <>
              <Text style={styles.label}>People to feed</Text>
              <TextInput
                style={styles.input}
                keyboardType="number-pad"
                value={household}
                onChangeText={setHousehold}
                placeholder="e.g. 10"
              />

              <Text style={styles.label}>Plan start date</Text>
              <Text style={styles.hint}>YYYY-MM-DD — anchors all sow dates.</Text>
              <TextInput
                style={styles.input}
                autoCapitalize="none"
                value={startDate}
                onChangeText={setStartDate}
                placeholder="2026-06-18"
              />

              <Text style={styles.note}>
                Changing people-to-feed rescales every crop that's on “auto” demand.
              </Text>

              {error ? <Text style={styles.error}>⚠️  {error}</Text> : null}

              <TouchableOpacity style={styles.saveBtn} onPress={save} disabled={saving}>
                {saving ? (
                  <ActivityIndicator color="#fff" />
                ) : (
                  <Text style={styles.saveText}>Save</Text>
                )}
              </TouchableOpacity>
            </>
          )}
          <TouchableOpacity onPress={onClose} disabled={saving}>
            <Text style={styles.cancel}>Cancel</Text>
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
    padding: 22, paddingBottom: 40,
  },
  title: { fontSize: 22, fontWeight: '800', color: '#222', marginBottom: 8 },
  label: { fontSize: 14, fontWeight: '700', color: '#444', marginTop: 14, marginBottom: 4 },
  hint: { fontSize: 12, color: '#999', marginBottom: 6 },
  input: {
    borderWidth: 1, borderColor: '#ccc', borderRadius: 10, padding: 12,
    fontSize: 16, backgroundColor: '#fff',
  },
  note: { fontSize: 12, color: '#888', marginTop: 12, lineHeight: 18 },
  error: { color: '#c0392b', marginTop: 14, fontSize: 13 },
  saveBtn: {
    backgroundColor: '#3a7d44', borderRadius: 10, padding: 15,
    alignItems: 'center', marginTop: 20,
  },
  saveText: { color: '#fff', fontSize: 16, fontWeight: '700' },
  cancel: { textAlign: 'center', color: '#888', marginTop: 16, fontSize: 15 },
});
