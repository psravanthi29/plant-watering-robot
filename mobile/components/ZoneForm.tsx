import { useState } from 'react';
import {
  ActivityIndicator,
  Modal,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from 'react-native';

export type ZoneInput = {
  name: string;
  sensor_key?: string | null;
  area_m2?: number | null;
  sun?: string | null;
  container_type?: string | null;
  max_water_seconds?: number | null;
  notes?: string | null;
};

export type ZoneExisting = ZoneInput & { id: number };

const SUN_OPTIONS = [
  { key: 'full', label: 'Full sun' },
  { key: 'partial', label: 'Partial' },
  { key: 'shade', label: 'Shade' },
];

const CONTAINER_OPTIONS = ['Raised bed', 'Pot', 'Grow bag', 'In-ground', 'Trough'];

function numOrNull(s: string): number | null {
  const t = s.trim();
  if (!t) return null;
  const n = Number(t);
  return Number.isFinite(n) ? n : null;
}

// Add/edit a zone. Controlled modal; the parent owns visibility and persistence
// (this component just gathers a clean ZoneInput and calls onSubmit).
export default function ZoneForm({
  visible,
  initial,
  onSubmit,
  onClose,
}: {
  visible: boolean;
  initial?: ZoneExisting | null;
  onSubmit: (data: ZoneInput) => Promise<void>;
  onClose: () => void;
}) {
  const editing = !!initial;
  const [name, setName] = useState(initial?.name ?? '');
  const [sensorKey, setSensorKey] = useState(initial?.sensor_key ?? '');
  const [area, setArea] = useState(
    initial?.area_m2 != null ? String(initial.area_m2) : ''
  );
  const [sun, setSun] = useState<string | null>(initial?.sun ?? 'full');
  const [container, setContainer] = useState<string | null>(
    initial?.container_type ?? null
  );
  const [maxSecs, setMaxSecs] = useState(
    initial?.max_water_seconds != null ? String(initial.max_water_seconds) : ''
  );
  const [notes, setNotes] = useState(initial?.notes ?? '');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function save() {
    if (!name.trim()) {
      setError('Give the zone a name.');
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await onSubmit({
        name: name.trim(),
        sensor_key: sensorKey.trim() || null,
        area_m2: numOrNull(area),
        sun,
        container_type: container,
        max_water_seconds: numOrNull(maxSecs),
        notes: notes.trim() || null,
      });
    } catch (e: any) {
      setError(e?.message ?? 'Could not save.');
      setSaving(false);
    }
  }

  return (
    <Modal visible={visible} animationType="slide" transparent onRequestClose={onClose}>
      <View style={styles.backdrop}>
        <View style={styles.sheet}>
          <ScrollView contentContainerStyle={styles.body} keyboardShouldPersistTaps="handled">
            <Text style={styles.title}>{editing ? 'Edit zone' : 'Add a zone'}</Text>

            <Text style={styles.label}>Name *</Text>
            <TextInput
              style={styles.input}
              placeholder="e.g. Balcony bed"
              value={name}
              onChangeText={setName}
            />

            <Text style={styles.label}>Sensor key</Text>
            <Text style={styles.hint}>
              The id your ESP32 reports (e.g. "zone-1"). Links live moisture to this zone.
            </Text>
            <TextInput
              style={styles.input}
              placeholder="zone-1"
              autoCapitalize="none"
              value={sensorKey ?? ''}
              onChangeText={setSensorKey}
            />

            <Text style={styles.label}>Area (m²)</Text>
            <TextInput
              style={styles.input}
              placeholder="e.g. 1.5"
              keyboardType="decimal-pad"
              value={area}
              onChangeText={setArea}
            />

            <Text style={styles.label}>Sun exposure</Text>
            <View style={styles.segment}>
              {SUN_OPTIONS.map((o) => (
                <Pressable
                  key={o.key}
                  style={[styles.segItem, sun === o.key && styles.segActive]}
                  onPress={() => setSun(o.key)}
                >
                  <Text style={[styles.segText, sun === o.key && styles.segActiveText]}>
                    {o.label}
                  </Text>
                </Pressable>
              ))}
            </View>

            <Text style={styles.label}>Container type</Text>
            <View style={styles.chips}>
              {CONTAINER_OPTIONS.map((c) => (
                <Pressable
                  key={c}
                  style={[styles.chip, container === c && styles.chipActive]}
                  onPress={() => setContainer(container === c ? null : c)}
                >
                  <Text style={[styles.chipText, container === c && styles.chipActiveText]}>
                    {c}
                  </Text>
                </Pressable>
              ))}
            </View>

            <Text style={styles.label}>Max water per run (seconds)</Text>
            <Text style={styles.hint}>Safety cap so a stuck valve can't flood. Optional.</Text>
            <TextInput
              style={styles.input}
              placeholder="e.g. 30"
              keyboardType="number-pad"
              value={maxSecs}
              onChangeText={setMaxSecs}
            />

            <Text style={styles.label}>Notes</Text>
            <TextInput
              style={[styles.input, styles.multiline]}
              placeholder="Anything to remember about this zone"
              multiline
              value={notes ?? ''}
              onChangeText={setNotes}
            />

            {error ? <Text style={styles.error}>⚠️  {error}</Text> : null}

            <TouchableOpacity style={styles.saveBtn} onPress={save} disabled={saving}>
              {saving ? (
                <ActivityIndicator color="#fff" />
              ) : (
                <Text style={styles.saveText}>{editing ? 'Save changes' : 'Add zone'}</Text>
              )}
            </TouchableOpacity>
            <TouchableOpacity onPress={onClose} disabled={saving}>
              <Text style={styles.cancel}>Cancel</Text>
            </TouchableOpacity>
          </ScrollView>
        </View>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  backdrop: { flex: 1, backgroundColor: 'rgba(0,0,0,0.35)', justifyContent: 'flex-end' },
  sheet: {
    backgroundColor: '#fcfcfa',
    borderTopLeftRadius: 18,
    borderTopRightRadius: 18,
    maxHeight: '92%',
  },
  body: { padding: 22, paddingBottom: 40 },
  title: { fontSize: 22, fontWeight: '800', color: '#222', marginBottom: 12 },
  label: { fontSize: 14, fontWeight: '700', color: '#444', marginTop: 14, marginBottom: 4 },
  hint: { fontSize: 12, color: '#999', marginBottom: 6 },
  input: {
    borderWidth: 1, borderColor: '#ccc', borderRadius: 10, padding: 12,
    fontSize: 16, backgroundColor: '#fff',
  },
  multiline: { minHeight: 64, textAlignVertical: 'top' },
  segment: { flexDirection: 'row', gap: 8 },
  segItem: {
    flex: 1, paddingVertical: 10, borderRadius: 10, borderWidth: 1,
    borderColor: '#ccc', backgroundColor: '#fff', alignItems: 'center',
  },
  segActive: { backgroundColor: '#3a7d44', borderColor: '#3a7d44' },
  segText: { fontSize: 14, color: '#444', fontWeight: '600' },
  segActiveText: { color: '#fff' },
  chips: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  chip: {
    paddingVertical: 8, paddingHorizontal: 14, borderRadius: 20,
    borderWidth: 1, borderColor: '#ccc', backgroundColor: '#fff',
  },
  chipActive: { backgroundColor: '#eef5ee', borderColor: '#3a7d44' },
  chipText: { fontSize: 13, color: '#555' },
  chipActiveText: { color: '#2f6b3a', fontWeight: '700' },
  error: { color: '#c0392b', marginTop: 14, fontSize: 13 },
  saveBtn: {
    backgroundColor: '#3a7d44', borderRadius: 10, padding: 15,
    alignItems: 'center', marginTop: 22,
  },
  saveText: { color: '#fff', fontSize: 16, fontWeight: '700' },
  cancel: { textAlign: 'center', color: '#888', marginTop: 16, fontSize: 15 },
});
