import { useCallback, useEffect, useState } from 'react';
import {
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from 'react-native';
import { apiFetch } from '../lib/api';
import Loading from './Loading';
import ListPickerModal, { PickerOption } from './ListPickerModal';

type Plan = { plants_needed: number; area_m2: number; type: string };
type Crop = {
  id: number;
  key: string;
  display: string;
  water_need: 'high' | 'medium' | 'low';
  sun_need: 'full' | 'partial' | 'shade';
  zone_id?: number | null;
  plan: Plan;
};
type Zone = { id: number; name: string; sun?: string | null; crops: string[] };
type LibraryItem = {
  key: string;
  display: string;
  category: string;
  water_need: string;
  sun_need: string;
};
type Assignment = {
  crop_id: number | null;
  display: string;
  zone_id: number;
  zone_name: string;
  water_need: string;
};
type Unplaced = { crop_id: number | null; display: string; water_need: string; reason: string };
type Placement = { assignments: Assignment[]; unplaced: Unplaced[] };

const WATER_COLOR: Record<string, string> = {
  high: '#1a6faf',
  medium: '#3a7d44',
  low: '#e07b00',
};
const SUN_ICON: Record<string, string> = { full: '☀️', partial: '⛅', shade: '☁️' };

function friendlyError(err: any): string {
  const msg = err?.message ?? String(err);
  if (/failed to fetch|network request failed|did not respond/i.test(msg)) {
    return 'Could not reach the server — it may be waking up. Pull to refresh in a few seconds.';
  }
  if (/API 401/.test(msg)) return 'Session expired. Pull to refresh or sign in again.';
  return msg;
}

export default function Planner() {
  const [crops, setCrops] = useState<Crop[]>([]);
  const [zones, setZones] = useState<Zone[]>([]);
  const [library, setLibrary] = useState<LibraryItem[]>([]);
  const [suggestion, setSuggestion] = useState<Placement | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [addOpen, setAddOpen] = useState(false);
  const [zonePickFor, setZonePickFor] = useState<Crop | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const [c, z, lib] = await Promise.all([
        apiFetch<Crop[]>('/api/crops'),
        apiFetch<Zone[]>('/api/zones'),
        apiFetch<LibraryItem[]>('/api/library'),
      ]);
      setCrops(c);
      setZones(z);
      setLibrary(lib);
    } catch (e) {
      setError(friendlyError(e));
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const zoneName = (id?: number | null) =>
    id == null ? null : zones.find((z) => z.id === id)?.name ?? `zone ${id}`;

  async function run(fn: () => Promise<any>) {
    setBusy(true);
    setError(null);
    try {
      await fn();
      await load();
    } catch (e) {
      setError(friendlyError(e));
    } finally {
      setBusy(false);
    }
  }

  function addCrop(key: string) {
    setAddOpen(false);
    run(() => apiFetch('/api/crops', { method: 'POST', body: JSON.stringify({ library_key: key }) }));
  }

  function removeCrop(c: Crop) {
    run(() => apiFetch(`/api/crops/${c.id}`, { method: 'DELETE' }));
  }

  function setZone(crop: Crop, zoneId: number | null) {
    setZonePickFor(null);
    run(() =>
      apiFetch(`/api/crops/${crop.id}/zone`, {
        method: 'POST',
        body: JSON.stringify({ zone_id: zoneId }),
      })
    );
  }

  async function suggest() {
    setBusy(true);
    setError(null);
    try {
      setSuggestion(await apiFetch<Placement>('/api/placement'));
    } catch (e) {
      setError(friendlyError(e));
    } finally {
      setBusy(false);
    }
  }

  function applySuggestion() {
    setSuggestion(null);
    run(() => apiFetch('/api/placement/apply', { method: 'POST' }));
  }

  if (loading) return <Loading />;

  const libOptions: PickerOption[] = library.map((l) => ({
    key: l.key,
    label: l.display,
    sublabel: `${l.category} · ${l.water_need} water · ${l.sun_need} sun`,
  }));
  const zoneOptions: PickerOption[] = [
    ...zones.map((z) => ({ key: String(z.id), label: z.name, sublabel: z.sun ?? undefined })),
    { key: 'none', label: 'Unassign', sublabel: 'remove from its zone' },
  ];

  return (
    <View style={styles.container}>
      <View style={styles.topbar}>
        <Text style={styles.title}>📋 Planner</Text>
        <TouchableOpacity style={styles.addBtn} onPress={() => setAddOpen(true)} disabled={busy}>
          <Text style={styles.addText}>+ Add crop</Text>
        </TouchableOpacity>
      </View>

      <ScrollView
        contentContainerStyle={{ padding: 14 }}
        refreshControl={
          <RefreshControl
            refreshing={refreshing}
            onRefresh={() => {
              setRefreshing(true);
              load();
            }}
          />
        }
      >
        {error ? (
          <View style={styles.errorBox}>
            <Text style={styles.error}>{error}</Text>
          </View>
        ) : null}

        {/* Crops */}
        <Text style={styles.section}>My crops ({crops.length})</Text>
        {crops.length === 0 ? (
          <Text style={styles.empty}>
            No crops yet. Tap “+ Add crop” to pick what you want to grow; the planner
            works out plant counts and which zone each should go in.
          </Text>
        ) : (
          crops.map((c) => (
            <View key={c.id} style={styles.card}>
              <View style={styles.cardHeader}>
                <Text style={styles.cropName}>{c.display}</Text>
                <TouchableOpacity onPress={() => removeCrop(c)} disabled={busy}>
                  <Text style={styles.remove}>Remove</Text>
                </TouchableOpacity>
              </View>
              <View style={styles.badges}>
                <View style={[styles.badge, { backgroundColor: WATER_COLOR[c.water_need] }]}>
                  <Text style={styles.badgeText}>💧 {c.water_need}</Text>
                </View>
                <Text style={styles.sun}>
                  {SUN_ICON[c.sun_need] ?? ''} {c.sun_need} sun
                </Text>
              </View>
              <Text style={styles.meta}>
                {c.plan.plants_needed} plants · {c.plan.area_m2} m²
              </Text>
              <TouchableOpacity style={styles.zoneRow} onPress={() => setZonePickFor(c)} disabled={busy}>
                <Text style={styles.zoneLabel}>
                  {c.zone_id != null ? `Zone: ${zoneName(c.zone_id)}` : 'Not placed in a zone'}
                </Text>
                <Text style={styles.zoneChange}>{c.zone_id != null ? 'Change' : 'Place'}</Text>
              </TouchableOpacity>
            </View>
          ))
        )}

        {/* Auto-suggest */}
        {crops.length > 0 && zones.length > 0 ? (
          <TouchableOpacity style={styles.suggestBtn} onPress={suggest} disabled={busy}>
            <Text style={styles.suggestText}>✨ Auto-suggest placement</Text>
          </TouchableOpacity>
        ) : null}
        {crops.length > 0 && zones.length === 0 ? (
          <Text style={styles.hint}>Add zones in the Setup tab to place these crops.</Text>
        ) : null}

        {/* Suggestion preview */}
        {suggestion ? (
          <View style={styles.suggestBox}>
            <Text style={styles.section}>Suggested placement</Text>
            {suggestion.assignments.map((a, i) => (
              <Text key={`a${i}`} style={styles.assignLine}>
                ✅ {a.display} → <Text style={styles.bold}>{a.zone_name}</Text>
              </Text>
            ))}
            {suggestion.unplaced.map((u, i) => (
              <Text key={`u${i}`} style={styles.unplacedLine}>
                ⚠️ {u.display} — {u.reason}
              </Text>
            ))}
            {suggestion.assignments.length === 0 && suggestion.unplaced.length === 0 ? (
              <Text style={styles.hint}>Nothing to place.</Text>
            ) : null}
            <View style={styles.applyRow}>
              <TouchableOpacity onPress={() => setSuggestion(null)}>
                <Text style={styles.dismiss}>Dismiss</Text>
              </TouchableOpacity>
              {suggestion.assignments.length > 0 ? (
                <TouchableOpacity style={styles.applyBtn} onPress={applySuggestion} disabled={busy}>
                  <Text style={styles.applyText}>Apply</Text>
                </TouchableOpacity>
              ) : null}
            </View>
          </View>
        ) : null}
      </ScrollView>

      <ListPickerModal
        visible={addOpen}
        title="Add a crop"
        options={libOptions}
        onPick={addCrop}
        onClose={() => setAddOpen(false)}
        emptyText="Library is empty."
      />
      <ListPickerModal
        visible={zonePickFor != null}
        title={zonePickFor ? `Place “${zonePickFor.display}”` : 'Place crop'}
        options={zoneOptions}
        onPick={(key) => zonePickFor && setZone(zonePickFor, key === 'none' ? null : Number(key))}
        onClose={() => setZonePickFor(null)}
        emptyText="No zones yet — add one in Setup."
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#fcfcfa' },
  topbar: {
    flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center',
    paddingTop: 56, paddingHorizontal: 18, paddingBottom: 12,
    borderBottomWidth: 1, borderBottomColor: '#eee', backgroundColor: '#fff',
  },
  title: { fontSize: 22, fontWeight: '800', color: '#222' },
  addBtn: { backgroundColor: '#3a7d44', paddingVertical: 8, paddingHorizontal: 14, borderRadius: 8 },
  addText: { color: '#fff', fontWeight: '700' },
  errorBox: { backgroundColor: '#fdecea', padding: 12, borderRadius: 10, marginBottom: 10 },
  error: { color: '#c0392b', fontSize: 13 },
  section: { fontSize: 15, fontWeight: '800', color: '#444', marginTop: 8, marginBottom: 8 },
  empty: { color: '#999', lineHeight: 20, paddingVertical: 10 },
  hint: { color: '#888', fontSize: 13, marginTop: 8, lineHeight: 19 },
  card: {
    backgroundColor: '#fff', borderRadius: 12, padding: 16, marginBottom: 10,
    borderWidth: 1, borderColor: '#ececec',
  },
  cardHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  cropName: { fontSize: 17, fontWeight: '700', color: '#222' },
  remove: { color: '#c0392b', fontWeight: '700', fontSize: 13 },
  badges: { flexDirection: 'row', alignItems: 'center', gap: 10, marginTop: 8 },
  badge: { borderRadius: 12, paddingVertical: 3, paddingHorizontal: 10 },
  badgeText: { color: '#fff', fontSize: 12, fontWeight: '700' },
  sun: { fontSize: 13, color: '#777' },
  meta: { fontSize: 13, color: '#777', marginTop: 8 },
  zoneRow: {
    flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center',
    marginTop: 12, paddingTop: 12, borderTopWidth: 1, borderTopColor: '#f0f0f0',
  },
  zoneLabel: { fontSize: 14, color: '#444' },
  zoneChange: { fontSize: 14, color: '#1a6faf', fontWeight: '700' },
  suggestBtn: {
    backgroundColor: '#eef5ee', borderWidth: 1, borderColor: '#cfe3cf',
    borderRadius: 10, padding: 14, alignItems: 'center', marginTop: 10,
  },
  suggestText: { color: '#2f6b3a', fontWeight: '700', fontSize: 15 },
  suggestBox: {
    backgroundColor: '#fff', borderRadius: 12, padding: 16, marginTop: 12,
    borderWidth: 1, borderColor: '#ececec',
  },
  assignLine: { fontSize: 14, color: '#333', marginVertical: 3, lineHeight: 20 },
  unplacedLine: { fontSize: 14, color: '#b36200', marginVertical: 3, lineHeight: 20 },
  bold: { fontWeight: '800' },
  applyRow: { flexDirection: 'row', justifyContent: 'flex-end', alignItems: 'center', gap: 18, marginTop: 14 },
  dismiss: { color: '#888', fontSize: 15 },
  applyBtn: { backgroundColor: '#3a7d44', paddingVertical: 10, paddingHorizontal: 22, borderRadius: 8 },
  applyText: { color: '#fff', fontWeight: '700', fontSize: 15 },
});
