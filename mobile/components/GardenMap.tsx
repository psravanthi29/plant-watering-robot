import { useCallback, useEffect, useRef, useState } from 'react';
import {
  GestureResponderEvent,
  Platform,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from 'react-native';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { apiFetch } from '../lib/api';
import Loading from './Loading';
import ListPickerModal, { PickerOption } from './ListPickerModal';

// Storage is always cm (unit-agnostic); units only affect display/entry. ft mode
// uses a 1-ft grid, m mode a 0.5-m grid. Area converts m² → ft² (×10.7639).
type Unit = 'm' | 'ft';
const UNITS: Record<Unit, {
  label: string; toDisp: (cm: number) => number; toCm: (v: number) => number;
  gridCm: number; gridLabel: string; areaDisp: (m2: number) => number; areaLabel: string; dec: number;
}> = {
  m: { label: 'm', toDisp: (cm) => cm / 100, toCm: (v) => v * 100, gridCm: 50,
       gridLabel: '0.5 m', areaDisp: (m2) => m2, areaLabel: 'm²', dec: 2 },
  ft: { label: 'ft', toDisp: (cm) => cm / 30.48, toCm: (v) => v * 30.48, gridCm: 30.48,
        gridLabel: '1 ft', areaDisp: (m2) => m2 * 10.7639, areaLabel: 'ft²', dec: 1 },
};

// One physical object on the garden map. Coordinates + sizes are real-world cm;
// the canvas just scales cm → px. A circle uses width_cm as its diameter.
type Feature = {
  id: number;
  name: string | null;
  template: string | null;
  kind: string | null;
  shape: 'rect' | 'circle';
  width_cm: number;
  length_cm: number;
  x_cm: number;
  y_cm: number;
  sun: string | null;
  zone_id: number | null;
  area_m2: number;
};
type Zone = { id: number; name: string };

// Palette of pre-configured templates: pick one, it drops on the canvas, then you
// set its exact size. Defaults are typical real sizes (cm).
type Template = {
  key: string;
  label: string;
  icon: string;
  kind: 'bed' | 'container';
  shape: 'rect' | 'circle';
  w: number;
  l: number;
  color: string;
};
const TEMPLATES: Template[] = [
  { key: 'raised_bed', label: 'Raised bed', icon: '🟫', kind: 'bed', shape: 'rect', w: 120, l: 60, color: '#b5835a' },
  { key: 'in_ground', label: 'In-ground', icon: '🟩', kind: 'bed', shape: 'rect', w: 200, l: 100, color: '#7aa86f' },
  { key: 'pot', label: 'Pot', icon: '🪴', kind: 'container', shape: 'circle', w: 30, l: 30, color: '#c97b54' },
  { key: 'grow_bag', label: 'Grow bag', icon: '🛍️', kind: 'container', shape: 'circle', w: 35, l: 35, color: '#8a9bb0' },
  { key: 'drum', label: 'Drum', icon: '🛢️', kind: 'container', shape: 'circle', w: 56, l: 56, color: '#6d7b8a' },
  { key: 'trough', label: 'Trough', icon: '🪟', kind: 'container', shape: 'rect', w: 60, l: 25, color: '#9a8c7a' },
  { key: 'seed_tray', label: 'Seed tray', icon: '🌱', kind: 'container', shape: 'rect', w: 50, l: 30, color: '#7fa779' },
];
const TEMPLATE_BY_KEY = Object.fromEntries(TEMPLATES.map((t) => [t.key, t]));

const ZONE_COLORS = ['#3a7d44', '#1a6faf', '#e07b00', '#6a4caf', '#c0392b', '#138d75', '#b8860b'];
const zoneColor = (zoneId: number) => ZONE_COLORS[zoneId % ZONE_COLORS.length];

function friendlyError(err: any): string {
  const msg = err?.message ?? String(err);
  if (/failed to fetch|network request failed|did not respond/i.test(msg)) {
    return 'Could not reach the server — it may be waking up. Pull to refresh in a few seconds.';
  }
  if (/API 401/.test(msg)) return 'Session expired. Sign in again.';
  return msg;
}
function clamp(v: number, lo: number, hi: number) {
  return Math.max(lo, Math.min(hi, v));
}

export default function GardenMap() {
  const [features, setFeatures] = useState<Feature[]>([]);
  const [zones, setZones] = useState<Zone[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [zonePickOpen, setZonePickOpen] = useState(false);

  // Display unit (m/ft). Persisted so it sticks between visits. Storage stays cm.
  const [unit, setUnit] = useState<Unit>('m');
  useEffect(() => {
    AsyncStorage.getItem('garden_unit').then((v) => {
      if (v === 'm' || v === 'ft') setUnit(v);
    });
  }, []);
  function changeUnit(u: Unit) {
    setUnit(u);
    AsyncStorage.setItem('garden_unit', u).catch(() => {});
  }
  const U = UNITS[unit];
  const disp = (cm: number) => {
    const v = U.toDisp(cm);
    return Number.isInteger(v) ? String(v) : v.toFixed(U.dec);
  };
  // Parse a value typed in the current unit back to cm; fall back (in cm) if blank/invalid.
  const parseCm = (text: string, fallbackCm: number) => {
    const n = Number(text);
    return Number.isFinite(n) && n > 0 ? U.toCm(n) : fallbackCm;
  };

  // Garden extent (cm). Local view state for v1 — features keep absolute coords.
  const [gardenW, setGardenW] = useState(600);
  const [gardenH, setGardenH] = useState(450);
  const [canvasPx, setCanvasPx] = useState(0); // measured px width of the canvas
  const scale = canvasPx > 0 ? canvasPx / gardenW : 0;

  const dragRef = useRef<{
    id: number; startX: number; startY: number; origX: number; origY: number; moved: boolean;
  } | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const [f, z] = await Promise.all([
        apiFetch<Feature[]>('/api/features'),
        apiFetch<Zone[]>('/api/zones'),
      ]);
      setFeatures(f);
      setZones(z);
    } catch (e) {
      setError(friendlyError(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const selected = features.find((f) => f.id === selectedId) ?? null;
  const extentX = (f: Feature) => f.width_cm;
  const extentY = (f: Feature) => (f.shape === 'circle' ? f.width_cm : f.length_cm);

  function patchFeature(id: number, fields: Partial<Feature>) {
    apiFetch(`/api/features/${id}`, { method: 'PATCH', body: JSON.stringify(fields) }).catch(
      (e) => setError(friendlyError(e))
    );
  }

  // Apply a dimension edit (update local state + persist). Wired to BOTH blur
  // (onEndEditing) and Enter (onSubmitEditing) so desktop saves reliably.
  function saveDim(id: number, fields: Partial<Feature>) {
    setFeatures((p) => p.map((x) => (x.id === id ? { ...x, ...fields } : x)));
    patchFeature(id, fields);
  }

  // ---- drag (works on web mouse + native touch via the responder system) ----
  function onGrant(f: Feature, e: GestureResponderEvent) {
    setSelectedId(f.id);
    dragRef.current = {
      id: f.id,
      startX: e.nativeEvent.pageX,
      startY: e.nativeEvent.pageY,
      origX: f.x_cm,
      origY: f.y_cm,
      moved: false,
    };
  }
  function onMove(e: GestureResponderEvent) {
    const d = dragRef.current;
    if (!d || scale === 0) return;
    const f = features.find((x) => x.id === d.id);
    if (!f) return;
    const dxCm = (e.nativeEvent.pageX - d.startX) / scale;
    const dyCm = (e.nativeEvent.pageY - d.startY) / scale;
    if (Math.abs(dxCm) > 1 || Math.abs(dyCm) > 1) d.moved = true;
    const nx = clamp(d.origX + dxCm, 0, gardenW - extentX(f));
    const ny = clamp(d.origY + dyCm, 0, gardenH - extentY(f));
    setFeatures((prev) => prev.map((x) => (x.id === d.id ? { ...x, x_cm: nx, y_cm: ny } : x)));
  }
  function onRelease() {
    const d = dragRef.current;
    dragRef.current = null;
    if (!d || !d.moved) return;
    const f = features.find((x) => x.id === d.id);
    if (f) patchFeature(f.id, { x_cm: Math.round(f.x_cm), y_cm: Math.round(f.y_cm) });
  }

  async function addFromTemplate(t: Template) {
    setError(null);
    try {
      const res = await apiFetch<{ id: number }>('/api/features', {
        method: 'POST',
        body: JSON.stringify({
          name: t.label, template: t.key, kind: t.kind, shape: t.shape,
          width_cm: t.w, length_cm: t.l, x_cm: 20, y_cm: 20, sun: 'full',
        }),
      });
      await load();
      setSelectedId(res.id);
    } catch (e) {
      setError(friendlyError(e));
    }
  }

  function deleteFeature(f: Feature) {
    const yes = () => {
      apiFetch(`/api/features/${f.id}`, { method: 'DELETE' })
        .then(load)
        .catch((e) => setError(friendlyError(e)));
      setSelectedId(null);
    };
    if (Platform.OS === 'web') {
      if (window.confirm(`Delete "${f.name ?? 'feature'}"?`)) yes();
    } else {
      yes();
    }
  }

  if (loading) return <Loading />;

  const zoneName = (id: number | null) =>
    id == null ? null : zones.find((z) => z.id === id)?.name ?? `zone ${id}`;
  const zoneOptions: PickerOption[] = [
    ...zones.map((z) => ({ key: String(z.id), label: z.name })),
    { key: 'none', label: 'Unassign', sublabel: 'not in a watering zone' },
  ];

  return (
    <View style={styles.container}>
      <View style={styles.topbar}>
        <Text style={styles.title}>🗺 Garden map</Text>
        <View style={styles.topRight}>
          <Text style={styles.scaleNote}>grid = {U.gridLabel}</Text>
          <View style={styles.unitToggle}>
            {(['m', 'ft'] as Unit[]).map((u) => (
              <TouchableOpacity
                key={u}
                style={[styles.unitBtn, unit === u && styles.unitBtnActive]}
                onPress={() => changeUnit(u)}
              >
                <Text style={[styles.unitBtnText, unit === u && styles.unitBtnTextActive]}>{u}</Text>
              </TouchableOpacity>
            ))}
          </View>
        </View>
      </View>

      <ScrollView contentContainerStyle={{ padding: 14 }}>
        {error ? (
          <View style={styles.errorBox}>
            <Text style={styles.error}>{error}</Text>
          </View>
        ) : null}

        {/* Palette */}
        <Text style={styles.label}>Add to your garden</Text>
        <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.palette}>
          {TEMPLATES.map((t) => (
            <TouchableOpacity key={t.key} style={styles.palItem} onPress={() => addFromTemplate(t)}>
              <Text style={styles.palIcon}>{t.icon}</Text>
              <Text style={styles.palLabel}>{t.label}</Text>
            </TouchableOpacity>
          ))}
        </ScrollView>

        {/* Garden size controls */}
        <View style={styles.sizeRow}>
          <Text style={styles.sizeLabel}>Garden size:</Text>
          <TextInput
            style={styles.sizeInput}
            keyboardType="decimal-pad"
            value={disp(gardenW)}
            onChangeText={(v) => setGardenW(Math.max(50, U.toCm(Number(v) || 1)))}
          />
          <Text style={styles.sizeX}>{U.label} ×</Text>
          <TextInput
            style={styles.sizeInput}
            keyboardType="decimal-pad"
            value={disp(gardenH)}
            onChangeText={(v) => setGardenH(Math.max(50, U.toCm(Number(v) || 1)))}
          />
          <Text style={styles.sizeX}>{U.label}</Text>
        </View>

        {/* Canvas */}
        <View
          style={styles.canvas}
          onLayout={(e) => setCanvasPx(e.nativeEvent.layout.width)}
        >
          {scale > 0 ? (
            <View style={{ width: '100%', height: gardenH * scale }}>
              {/* grid: 0.5 m (metric) or 1 ft (imperial) */}
              {Array.from({ length: Math.floor(gardenW / U.gridCm) + 1 }).map((_, i) => (
                <View key={`v${i}`} style={[styles.grid, { left: i * U.gridCm * scale, top: 0, width: 1, height: gardenH * scale }]} />
              ))}
              {Array.from({ length: Math.floor(gardenH / U.gridCm) + 1 }).map((_, i) => (
                <View key={`h${i}`} style={[styles.grid, { top: i * U.gridCm * scale, left: 0, height: 1, width: '100%' }]} />
              ))}

              {features.map((f) => {
                const w = extentX(f) * scale;
                const h = extentY(f) * scale;
                const sel = f.id === selectedId;
                const t = f.template ? TEMPLATE_BY_KEY[f.template] : null;
                const fill = (t?.color ?? '#8a9bb0') + 'cc';
                const border = f.zone_id != null ? zoneColor(f.zone_id) : sel ? '#222' : 'rgba(0,0,0,0.25)';
                return (
                  <View
                    key={f.id}
                    onStartShouldSetResponder={() => true}
                    onMoveShouldSetResponder={() => true}
                    onResponderGrant={(e) => onGrant(f, e)}
                    onResponderMove={onMove}
                    onResponderRelease={onRelease}
                    style={[
                      styles.feature,
                      {
                        left: f.x_cm * scale,
                        top: f.y_cm * scale,
                        width: w,
                        height: h,
                        backgroundColor: fill,
                        borderColor: border,
                        borderWidth: sel ? 3 : f.zone_id != null ? 2.5 : 1,
                        borderRadius: f.shape === 'circle' ? w / 2 : 6,
                      },
                    ]}
                  >
                    {w > 38 && h > 22 ? (
                      <Text style={styles.featLabel} numberOfLines={1}>
                        {f.name}
                      </Text>
                    ) : null}
                  </View>
                );
              })}
            </View>
          ) : null}
        </View>
        {features.length === 0 ? (
          <Text style={styles.hint}>
            Tap a template above to drop it on the canvas, then drag to position and tap it to
            set its exact size, sun, and watering zone.
          </Text>
        ) : (
          <Text style={styles.hint}>Drag to move · tap a shape to edit it.</Text>
        )}

        {/* Edit panel for the selected feature */}
        {selected ? (
          <View style={styles.panel}>
            <View style={styles.panelHead}>
              <Text style={styles.panelTitle}>
                {TEMPLATE_BY_KEY[selected.template ?? '']?.icon ?? '▫️'} Edit feature
              </Text>
              <Text style={styles.area}>{U.areaDisp(selected.area_m2).toFixed(U.dec)} {U.areaLabel}</Text>
            </View>

            <Text style={styles.fieldLabel}>Name</Text>
            <TextInput
              style={styles.input}
              value={selected.name ?? ''}
              onChangeText={(v) =>
                setFeatures((p) => p.map((x) => (x.id === selected.id ? { ...x, name: v } : x)))
              }
              onBlur={() => patchFeature(selected.id, { name: selected.name })}
            />

            {selected.shape === 'circle' ? (
              <>
                <Text style={styles.fieldLabel}>Diameter ({U.label})</Text>
                <TextInput
                  key={`dia-${unit}`}
                  style={styles.input}
                  keyboardType="decimal-pad"
                  returnKeyType="done"
                  defaultValue={disp(selected.width_cm)}
                  onEndEditing={(e) => {
                    const d = parseCm(e.nativeEvent.text, selected.width_cm);
                    saveDim(selected.id, { width_cm: d, length_cm: d });
                  }}
                  onSubmitEditing={(e) => {
                    const d = parseCm(e.nativeEvent.text, selected.width_cm);
                    saveDim(selected.id, { width_cm: d, length_cm: d });
                  }}
                />
              </>
            ) : (
              <View style={styles.dimRow}>
                <View style={styles.dimCol}>
                  <Text style={styles.fieldLabel}>Width ({U.label})</Text>
                  <TextInput
                    key={`w-${unit}`}
                    style={styles.input}
                    keyboardType="decimal-pad"
                    returnKeyType="done"
                    defaultValue={disp(selected.width_cm)}
                    onEndEditing={(e) => saveDim(selected.id, { width_cm: parseCm(e.nativeEvent.text, selected.width_cm) })}
                    onSubmitEditing={(e) => saveDim(selected.id, { width_cm: parseCm(e.nativeEvent.text, selected.width_cm) })}
                  />
                </View>
                <View style={styles.dimCol}>
                  <Text style={styles.fieldLabel}>Depth ({U.label})</Text>
                  <TextInput
                    key={`l-${unit}`}
                    style={styles.input}
                    keyboardType="decimal-pad"
                    returnKeyType="done"
                    defaultValue={disp(selected.length_cm)}
                    onEndEditing={(e) => saveDim(selected.id, { length_cm: parseCm(e.nativeEvent.text, selected.length_cm) })}
                    onSubmitEditing={(e) => saveDim(selected.id, { length_cm: parseCm(e.nativeEvent.text, selected.length_cm) })}
                  />
                </View>
              </View>
            )}

            <Text style={styles.fieldLabel}>Sun</Text>
            <View style={styles.segment}>
              {['full', 'partial', 'shade'].map((s) => (
                <TouchableOpacity
                  key={s}
                  style={[styles.seg, selected.sun === s && styles.segActive]}
                  onPress={() => {
                    setFeatures((p) => p.map((x) => (x.id === selected.id ? { ...x, sun: s } : x)));
                    patchFeature(selected.id, { sun: s });
                  }}
                >
                  <Text style={[styles.segText, selected.sun === s && styles.segActiveText]}>{s}</Text>
                </TouchableOpacity>
              ))}
            </View>

            <Text style={styles.fieldLabel}>Watering zone</Text>
            <TouchableOpacity style={styles.zoneBtn} onPress={() => setZonePickOpen(true)}>
              <Text style={styles.zoneBtnText}>
                {selected.zone_id != null ? zoneName(selected.zone_id) : 'Not in a zone'}
              </Text>
              <Text style={styles.zoneChange}>Change</Text>
            </TouchableOpacity>

            <View style={styles.panelActions}>
              <TouchableOpacity onPress={() => deleteFeature(selected)}>
                <Text style={styles.delete}>Delete</Text>
              </TouchableOpacity>
              <TouchableOpacity style={styles.doneBtn} onPress={() => setSelectedId(null)}>
                <Text style={styles.doneText}>Done</Text>
              </TouchableOpacity>
            </View>
          </View>
        ) : null}
      </ScrollView>

      <ListPickerModal
        visible={zonePickOpen}
        title="Assign to a watering zone"
        options={zoneOptions}
        onPick={(key) => {
          setZonePickOpen(false);
          if (!selected) return;
          const zid = key === 'none' ? null : Number(key);
          setFeatures((p) => p.map((x) => (x.id === selected.id ? { ...x, zone_id: zid } : x)));
          patchFeature(selected.id, { zone_id: zid });
        }}
        onClose={() => setZonePickOpen(false)}
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
  topRight: { alignItems: 'flex-end', gap: 4 },
  scaleNote: { fontSize: 12, color: '#999' },
  unitToggle: { flexDirection: 'row', borderWidth: 1, borderColor: '#ccc', borderRadius: 8, overflow: 'hidden' },
  unitBtn: { paddingVertical: 4, paddingHorizontal: 12, backgroundColor: '#fff' },
  unitBtnActive: { backgroundColor: '#3a7d44' },
  unitBtnText: { fontSize: 13, color: '#555', fontWeight: '700' },
  unitBtnTextActive: { color: '#fff' },
  errorBox: { backgroundColor: '#fdecea', padding: 12, borderRadius: 10, marginBottom: 10 },
  error: { color: '#c0392b', fontSize: 13 },
  label: { fontSize: 14, fontWeight: '800', color: '#444', marginBottom: 8 },
  palette: { flexGrow: 0, marginBottom: 14 },
  palItem: {
    alignItems: 'center', justifyContent: 'center', backgroundColor: '#fff',
    borderWidth: 1, borderColor: '#e3e3dd', borderRadius: 10, paddingVertical: 8,
    paddingHorizontal: 12, marginRight: 8, minWidth: 72,
  },
  palIcon: { fontSize: 22 },
  palLabel: { fontSize: 11, color: '#555', marginTop: 2, fontWeight: '600' },
  sizeRow: { flexDirection: 'row', alignItems: 'center', gap: 6, marginBottom: 10 },
  sizeLabel: { fontSize: 13, color: '#666', fontWeight: '600' },
  sizeInput: {
    borderWidth: 1, borderColor: '#ccc', borderRadius: 8, paddingVertical: 5,
    paddingHorizontal: 8, width: 54, fontSize: 14, backgroundColor: '#fff', textAlign: 'center',
  },
  sizeX: { fontSize: 13, color: '#888' },
  canvas: {
    backgroundColor: '#f3f1ea', borderWidth: 1, borderColor: '#ddd6c8',
    borderRadius: 10, overflow: 'hidden', minHeight: 80,
  },
  grid: { position: 'absolute', backgroundColor: 'rgba(120,110,90,0.13)' },
  feature: {
    position: 'absolute', alignItems: 'center', justifyContent: 'center',
    overflow: 'hidden',
    ...(Platform.OS === 'web' ? { cursor: 'grab' } as any : {}),
  },
  featLabel: { fontSize: 10, color: '#fff', fontWeight: '700', paddingHorizontal: 2 },
  hint: { fontSize: 13, color: '#888', marginTop: 10, lineHeight: 19 },
  panel: {
    backgroundColor: '#fff', borderRadius: 12, padding: 16, marginTop: 14,
    borderWidth: 1, borderColor: '#ececec',
  },
  panelHead: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  panelTitle: { fontSize: 16, fontWeight: '800', color: '#222' },
  area: { fontSize: 13, color: '#3a7d44', fontWeight: '700' },
  fieldLabel: { fontSize: 13, fontWeight: '700', color: '#555', marginTop: 12, marginBottom: 4 },
  input: {
    borderWidth: 1, borderColor: '#ccc', borderRadius: 8, padding: 10,
    fontSize: 15, backgroundColor: '#fff',
  },
  dimRow: { flexDirection: 'row', gap: 12 },
  dimCol: { flex: 1 },
  segment: { flexDirection: 'row', gap: 8 },
  seg: {
    flex: 1, paddingVertical: 9, borderRadius: 8, borderWidth: 1, borderColor: '#ccc',
    backgroundColor: '#fff', alignItems: 'center',
  },
  segActive: { backgroundColor: '#3a7d44', borderColor: '#3a7d44' },
  segText: { fontSize: 13, color: '#444', fontWeight: '600' },
  segActiveText: { color: '#fff' },
  zoneBtn: {
    flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center',
    borderWidth: 1, borderColor: '#ccc', borderRadius: 8, padding: 11, backgroundColor: '#fff',
  },
  zoneBtnText: { fontSize: 14, color: '#444' },
  zoneChange: { fontSize: 14, color: '#1a6faf', fontWeight: '700' },
  panelActions: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginTop: 18 },
  delete: { color: '#c0392b', fontWeight: '700', fontSize: 15 },
  doneBtn: { backgroundColor: '#3a7d44', paddingVertical: 10, paddingHorizontal: 24, borderRadius: 8 },
  doneText: { color: '#fff', fontWeight: '700', fontSize: 15 },
});
