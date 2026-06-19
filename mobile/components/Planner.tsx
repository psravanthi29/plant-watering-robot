import { useCallback, useEffect, useState } from 'react';
import {
  ActivityIndicator,
  Modal,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from 'react-native';
import { apiFetch } from '../lib/api';
import Loading from './Loading';
import ListPickerModal, { PickerOption } from './ListPickerModal';
import PlannerSettings from './PlannerSettings';
import CarePlanModal from './CarePlanModal';

type Plan = { plants_needed: number; area_m2: number; type: string; weekly_demand_kg: number };
type Crop = {
  id: number;
  key: string;
  display: string;
  water_need: 'high' | 'medium' | 'low';
  sun_need: 'full' | 'partial' | 'shade';
  zone_id?: number | null;
  weekly_demand_kg?: number | null;
  demand_auto: boolean;
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
type Task = {
  id: number;
  display: string;
  batch_size: number;
  sow_date: string;
  status: 'pending' | 'done';
  done_on: string | null;
};
type Settings = { household_size: number; plan_start_date: string };

const WATER_COLOR: Record<string, string> = {
  high: '#1a6faf',
  medium: '#3a7d44',
  low: '#e07b00',
};
const SUN_ICON: Record<string, string> = { full: '☀️', partial: '⛅', shade: '☁️' };

function todayISO(): string {
  return new Date().toISOString().slice(0, 10);
}
function plusDaysISO(days: number): string {
  const d = new Date();
  d.setDate(d.getDate() + days);
  return d.toISOString().slice(0, 10);
}

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
  const [tasks, setTasks] = useState<Task[]>([]);
  const [settings, setSettings] = useState<Settings | null>(null);
  const [suggestion, setSuggestion] = useState<Placement | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [addOpen, setAddOpen] = useState(false);
  const [zonePickFor, setZonePickFor] = useState<Crop | null>(null);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [careTaskId, setCareTaskId] = useState<number | null>(null);
  // Demand-override mini-modal state.
  const [demandFor, setDemandFor] = useState<Crop | null>(null);
  const [demandText, setDemandText] = useState('');

  const load = useCallback(async () => {
    setError(null);
    // Settle each independently: tasks/settings are newer endpoints that may not
    // be deployed yet, and one missing endpoint must not blank the whole screen
    // (e.g. wipe the crop library). Core data (crops/zones/library) drives the error.
    const [c, z, lib, t, s] = await Promise.allSettled([
      apiFetch<Crop[]>('/api/crops'),
      apiFetch<Zone[]>('/api/zones'),
      apiFetch<LibraryItem[]>('/api/library'),
      apiFetch<Task[]>('/api/tasks'),
      apiFetch<Settings>('/api/planner/settings'),
    ]);

    if (c.status === 'fulfilled') setCrops(c.value);
    if (z.status === 'fulfilled') setZones(z.value);
    if (lib.status === 'fulfilled') setLibrary(lib.value);
    setTasks(t.status === 'fulfilled' ? t.value : []);
    setSettings(s.status === 'fulfilled' ? s.value : null);

    // Only surface an error if the core data failed; best-effort extras stay quiet.
    const core = [c, z, lib].find((r) => r.status === 'rejected');
    setError(core ? friendlyError((core as PromiseRejectedResult).reason) : null);

    setLoading(false);
    setRefreshing(false);
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

  function openDemand(c: Crop) {
    setDemandFor(c);
    setDemandText(c.demand_auto ? '' : String(c.weekly_demand_kg ?? ''));
  }
  function saveDemand() {
    const c = demandFor;
    if (!c) return;
    const raw = demandText.trim();
    setDemandFor(null);
    run(() =>
      apiFetch(`/api/crops/${c.id}/demand`, {
        method: 'POST',
        body: JSON.stringify({ weekly_demand_kg: raw ? Number(raw) : null }),
      })
    );
  }

  function markSown(t: Task) {
    run(() => apiFetch(`/api/tasks/${t.id}/done`, { method: 'POST' }));
  }
  function undoSown(t: Task) {
    run(() => apiFetch(`/api/tasks/${t.id}/undo`, { method: 'POST' }));
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

  const today = todayISO();
  const soon = plusDaysISO(3);
  const pending = tasks.filter((t) => t.status === 'pending');
  const dueSowings = pending.filter((t) => t.sow_date <= soon).sort((a, b) => a.sow_date.localeCompare(b.sow_date));
  const laterCount = pending.length - dueSowings.length;
  const growing = tasks.filter((t) => t.status === 'done');

  return (
    <View style={styles.container}>
      <View style={styles.topbar}>
        <View>
          <Text style={styles.title}>📋 Planner</Text>
          {settings ? (
            <Text style={styles.subtitle}>
              Feeding {settings.household_size} · starts {settings.plan_start_date}
            </Text>
          ) : null}
        </View>
        <View style={styles.topActions}>
          <TouchableOpacity onPress={() => setSettingsOpen(true)} disabled={busy}>
            <Text style={styles.gear}>⚙️</Text>
          </TouchableOpacity>
          <TouchableOpacity style={styles.addBtn} onPress={() => setAddOpen(true)} disabled={busy}>
            <Text style={styles.addText}>+ Add crop</Text>
          </TouchableOpacity>
        </View>
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

        {/* Today: sow tasks + growing plantings */}
        {dueSowings.length > 0 ? (
          <>
            <Text style={styles.section}>🌰 Sow now</Text>
            {dueSowings.map((t) => {
              const overdue = t.sow_date < today;
              return (
                <View key={t.id} style={[styles.taskCard, overdue && styles.overdue]}>
                  <View style={styles.taskMain}>
                    <Text style={styles.taskWhen}>
                      {t.sow_date}
                      {overdue ? '  ⚠️ overdue' : ''}
                    </Text>
                    <Text style={styles.taskWhat}>
                      <Text style={styles.bold}>{t.batch_size}</Text> × {t.display}
                    </Text>
                  </View>
                  <TouchableOpacity style={styles.smallBtn} onPress={() => markSown(t)} disabled={busy}>
                    <Text style={styles.smallBtnText}>✓ Sown</Text>
                  </TouchableOpacity>
                </View>
              );
            })}
            {laterCount > 0 ? (
              <Text style={styles.hint}>+ {laterCount} more sowing(s) scheduled later.</Text>
            ) : null}
          </>
        ) : null}

        {growing.length > 0 ? (
          <>
            <Text style={styles.section}>🪴 Growing now</Text>
            {growing.map((t) => (
              <View key={t.id} style={styles.taskCard}>
                <View style={styles.taskMain}>
                  <Text style={styles.taskWhat}>
                    <Text style={styles.bold}>{t.display}</Text>
                  </Text>
                  <Text style={styles.taskWhen}>sown {t.done_on ?? t.sow_date}</Text>
                </View>
                <View style={styles.taskBtns}>
                  <TouchableOpacity style={styles.careBtn} onPress={() => setCareTaskId(t.id)} disabled={busy}>
                    <Text style={styles.careBtnText}>Care plan</Text>
                  </TouchableOpacity>
                  <TouchableOpacity onPress={() => undoSown(t)} disabled={busy}>
                    <Text style={styles.undo}>↩</Text>
                  </TouchableOpacity>
                </View>
              </View>
            ))}
          </>
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
              <TouchableOpacity style={styles.demandRow} onPress={() => openDemand(c)} disabled={busy}>
                <Text style={styles.demandText}>
                  {c.plan.weekly_demand_kg} kg/week{' '}
                  <Text style={styles.demandTag}>({c.demand_auto ? 'auto' : 'custom'})</Text>
                </Text>
                <Text style={styles.zoneChange}>Set need</Text>
              </TouchableOpacity>
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

      <PlannerSettings
        visible={settingsOpen}
        onClose={() => setSettingsOpen(false)}
        onSaved={load}
      />
      <CarePlanModal taskId={careTaskId} onClose={() => setCareTaskId(null)} />

      {/* Demand-override mini modal */}
      <Modal visible={demandFor != null} animationType="fade" transparent onRequestClose={() => setDemandFor(null)}>
        <View style={styles.demandBackdrop}>
          <View style={styles.demandSheet}>
            <Text style={styles.demandTitle}>
              Weekly need — {demandFor?.display}
            </Text>
            <Text style={styles.hint}>Kg per week. Leave blank to revert to auto.</Text>
            <TextInput
              style={styles.demandInput}
              keyboardType="decimal-pad"
              value={demandText}
              onChangeText={setDemandText}
              placeholder="e.g. 2.5"
              autoFocus
            />
            <View style={styles.demandActions}>
              <TouchableOpacity onPress={() => setDemandFor(null)}>
                <Text style={styles.dismiss}>Cancel</Text>
              </TouchableOpacity>
              <TouchableOpacity style={styles.applyBtn} onPress={saveDemand}>
                <Text style={styles.applyText}>Save</Text>
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>
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
  subtitle: { fontSize: 12, color: '#999', marginTop: 2 },
  topActions: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  gear: { fontSize: 22 },
  addBtn: { backgroundColor: '#3a7d44', paddingVertical: 8, paddingHorizontal: 14, borderRadius: 8 },
  addText: { color: '#fff', fontWeight: '700' },
  errorBox: { backgroundColor: '#fdecea', padding: 12, borderRadius: 10, marginBottom: 10 },
  error: { color: '#c0392b', fontSize: 13 },
  section: { fontSize: 15, fontWeight: '800', color: '#444', marginTop: 14, marginBottom: 8 },
  empty: { color: '#999', lineHeight: 20, paddingVertical: 10 },
  hint: { color: '#888', fontSize: 13, marginTop: 8, lineHeight: 19 },
  taskCard: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    backgroundColor: '#fff', borderRadius: 12, padding: 14, marginBottom: 8,
    borderWidth: 1, borderColor: '#ececec', gap: 10,
  },
  overdue: { borderLeftWidth: 4, borderLeftColor: '#e07b00' },
  taskMain: { flex: 1 },
  taskWhen: { fontSize: 12, color: '#3a7d44', fontWeight: '700' },
  taskWhat: { fontSize: 15, color: '#222', marginTop: 2 },
  taskBtns: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  smallBtn: { backgroundColor: '#3a7d44', paddingVertical: 8, paddingHorizontal: 14, borderRadius: 8 },
  smallBtnText: { color: '#fff', fontWeight: '700', fontSize: 13 },
  careBtn: {
    backgroundColor: '#fdf1e0', borderWidth: 1, borderColor: '#f0d6a8',
    paddingVertical: 8, paddingHorizontal: 12, borderRadius: 8,
  },
  careBtnText: { color: '#b36200', fontWeight: '700', fontSize: 13 },
  undo: { fontSize: 18, color: '#999', paddingHorizontal: 4 },
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
  demandRow: {
    flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center',
    marginTop: 10, paddingTop: 10, borderTopWidth: 1, borderTopColor: '#f0f0f0',
  },
  demandText: { fontSize: 14, color: '#444' },
  demandTag: { color: '#999', fontSize: 12 },
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
  demandBackdrop: {
    flex: 1, backgroundColor: 'rgba(0,0,0,0.35)', justifyContent: 'center', padding: 28,
  },
  demandSheet: { backgroundColor: '#fcfcfa', borderRadius: 16, padding: 22 },
  demandTitle: { fontSize: 18, fontWeight: '800', color: '#222', marginBottom: 6 },
  demandInput: {
    borderWidth: 1, borderColor: '#ccc', borderRadius: 10, padding: 12,
    fontSize: 16, backgroundColor: '#fff', marginTop: 8,
  },
  demandActions: { flexDirection: 'row', justifyContent: 'flex-end', alignItems: 'center', gap: 18, marginTop: 18 },
});
