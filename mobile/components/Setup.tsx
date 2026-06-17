import { useCallback, useEffect, useState } from 'react';
import {
  Alert,
  FlatList,
  Platform,
  RefreshControl,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from 'react-native';
import { apiFetch } from '../lib/api';
import ZoneForm, { ZoneExisting, ZoneInput } from './ZoneForm';
import Loading from './Loading';

type Zone = ZoneExisting & {
  recommended_target?: number | null;
  moisture_target?: number | null;
  crops: string[];
};

function friendlyError(err: any): string {
  const msg = err?.message ?? String(err);
  if (/failed to fetch|network request failed/i.test(msg)) {
    return 'Could not reach the server — it may be waking up. Tap Retry in a few seconds.';
  }
  if (/API 401/.test(msg)) return 'Session expired. Pull to refresh or sign in again.';
  return msg;
}

// Cross-platform confirm: window.confirm on web, Alert on native.
function confirmDelete(name: string, onYes: () => void) {
  if (Platform.OS === 'web') {
    // eslint-disable-next-line no-alert
    if (window.confirm(`Delete "${name}"? Crops in it will be unassigned.`)) onYes();
    return;
  }
  Alert.alert('Delete zone', `Delete "${name}"? Crops in it will be unassigned.`, [
    { text: 'Cancel', style: 'cancel' },
    { text: 'Delete', style: 'destructive', onPress: onYes },
  ]);
}

export default function Setup() {
  const [zones, setZones] = useState<Zone[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<Zone | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const data = await apiFetch<Zone[]>('/api/zones');
      setZones(data);
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

  function openAdd() {
    setEditing(null);
    setFormOpen(true);
  }

  function openEdit(z: Zone) {
    setEditing(z);
    setFormOpen(true);
  }

  async function submit(data: ZoneInput) {
    if (editing) {
      await apiFetch(`/api/zones/${editing.id}`, {
        method: 'PATCH',
        body: JSON.stringify(data),
      });
    } else {
      await apiFetch('/api/zones', { method: 'POST', body: JSON.stringify(data) });
    }
    setFormOpen(false);
    setEditing(null);
    setLoading(true);
    await load();
  }

  async function del(z: Zone) {
    confirmDelete(z.name, async () => {
      try {
        await apiFetch(`/api/zones/${z.id}`, { method: 'DELETE' });
        setLoading(true);
        await load();
      } catch (e) {
        setError(friendlyError(e));
      }
    });
  }

  function renderZone({ item }: { item: Zone }) {
    const sun = item.sun ? item.sun[0].toUpperCase() + item.sun.slice(1) : null;
    const meta = [
      item.area_m2 != null ? `${item.area_m2} m²` : null,
      sun,
      item.container_type,
    ].filter(Boolean);
    return (
      <View style={styles.card}>
        <View style={styles.cardHeader}>
          <Text style={styles.zoneName}>{item.name}</Text>
          <Text style={styles.sensorKey}>
            {item.sensor_key ? item.sensor_key : 'no sensor'}
          </Text>
        </View>
        {meta.length ? <Text style={styles.meta}>{meta.join('  ·  ')}</Text> : null}
        <Text style={styles.crops}>
          {item.crops?.length ? item.crops.join(', ') : 'No crops yet'}
        </Text>
        <View style={styles.actions}>
          <TouchableOpacity onPress={() => openEdit(item)}>
            <Text style={styles.edit}>Edit</Text>
          </TouchableOpacity>
          <TouchableOpacity onPress={() => del(item)}>
            <Text style={styles.delete}>Delete</Text>
          </TouchableOpacity>
        </View>
      </View>
    );
  }

  if (loading) {
    return <Loading />;
  }

  return (
    <View style={styles.container}>
      <View style={styles.topbar}>
        <Text style={styles.title}>🪴 Setup</Text>
        <TouchableOpacity style={styles.addBtn} onPress={openAdd}>
          <Text style={styles.addText}>+ Add zone</Text>
        </TouchableOpacity>
      </View>

      {error ? (
        <View style={styles.errorBox}>
          <Text style={styles.error}>{error}</Text>
          <TouchableOpacity
            style={styles.retry}
            onPress={() => {
              setLoading(true);
              load();
            }}
          >
            <Text style={styles.retryText}>Retry</Text>
          </TouchableOpacity>
        </View>
      ) : null}

      <FlatList
        data={zones}
        keyExtractor={(z) => String(z.id)}
        renderItem={renderZone}
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
        ListEmptyComponent={
          <View style={styles.empty}>
            <Text style={styles.emptyText}>
              No zones yet. A zone is one patch served by one moisture sensor and one
              valve. Add your beds or containers here, then the Planner can place crops
              into them.
            </Text>
            <TouchableOpacity style={styles.emptyBtn} onPress={openAdd}>
              <Text style={styles.addText}>+ Add your first zone</Text>
            </TouchableOpacity>
          </View>
        }
      />

      {formOpen ? (
        <ZoneForm
          visible={formOpen}
          initial={editing}
          onSubmit={submit}
          onClose={() => {
            setFormOpen(false);
            setEditing(null);
          }}
        />
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#fcfcfa' },
  center: { flex: 1, justifyContent: 'center', alignItems: 'center' },
  topbar: {
    flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center',
    paddingTop: 56, paddingHorizontal: 18, paddingBottom: 12,
    borderBottomWidth: 1, borderBottomColor: '#eee', backgroundColor: '#fff',
  },
  title: { fontSize: 22, fontWeight: '800', color: '#222' },
  addBtn: { backgroundColor: '#3a7d44', paddingVertical: 8, paddingHorizontal: 14, borderRadius: 8 },
  addText: { color: '#fff', fontWeight: '700' },
  errorBox: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    backgroundColor: '#fdecea', padding: 12, margin: 12, borderRadius: 10, gap: 10,
  },
  error: { color: '#c0392b', flex: 1, fontSize: 13 },
  retry: { backgroundColor: '#c0392b', paddingVertical: 8, paddingHorizontal: 16, borderRadius: 8 },
  retryText: { color: '#fff', fontWeight: '700' },
  card: {
    backgroundColor: '#fff', borderRadius: 12, padding: 16, marginBottom: 10,
    borderWidth: 1, borderColor: '#ececec',
  },
  cardHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  zoneName: { fontSize: 17, fontWeight: '700', color: '#222' },
  sensorKey: { fontSize: 12, color: '#3a7d44' },
  meta: { fontSize: 13, color: '#777', marginTop: 4 },
  crops: { fontSize: 13, color: '#555', marginTop: 6 },
  actions: { flexDirection: 'row', gap: 22, marginTop: 12 },
  edit: { color: '#1a6faf', fontWeight: '700', fontSize: 14 },
  delete: { color: '#c0392b', fontWeight: '700', fontSize: 14 },
  empty: { padding: 30, alignItems: 'center' },
  emptyText: { textAlign: 'center', color: '#999', lineHeight: 20, marginBottom: 18 },
  emptyBtn: { backgroundColor: '#3a7d44', paddingVertical: 12, paddingHorizontal: 20, borderRadius: 10 },
});
