import { useCallback, useEffect, useState } from 'react';
import {
  FlatList,
  RefreshControl,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from 'react-native';
import { apiFetch } from '../lib/api';
import { supabase } from '../lib/supabase';
import Loading from './Loading';

type Zone = {
  id: number;
  name: string;
  sensor_key?: string | null;
  moisture_target?: number | null;
  recommended_target?: number | null;
  crops: string[];
};

type Reading = { zone: string; value: number; timestamp: string };

// The Render free tier sleeps when idle; the first call while it wakes can fail
// at the network level ("Failed to fetch"). Turn that into a helpful message.
function friendlyError(err: any): string {
  const msg = err?.message ?? String(err);
  if (/failed to fetch|network request failed/i.test(msg)) {
    return 'Could not reach the server — it may be waking up. Tap Retry in a few seconds.';
  }
  if (/API 401/.test(msg)) return 'Session expired. Pull to refresh or sign in again.';
  return msg;
}

export default function Dashboard({ email }: { email?: string }) {
  const [zones, setZones] = useState<Zone[]>([]);
  const [latest, setLatest] = useState<Record<string, Reading>>({});
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    // Load each endpoint independently so one slow/cold call can't blank the
    // whole screen. Zones are the primary data; readings are best-effort.
    const [zoneRes, readingRes] = await Promise.allSettled([
      apiFetch<Zone[]>('/api/zones'),
      apiFetch<Reading[]>('/api/readings'),
    ]);

    if (zoneRes.status === 'fulfilled') {
      setZones(zoneRes.value);
    } else {
      setError(friendlyError(zoneRes.reason));
    }

    if (readingRes.status === 'fulfilled') {
      const byZone: Record<string, Reading> = {};
      for (const r of readingRes.value) if (!byZone[r.zone]) byZone[r.zone] = r;
      setLatest(byZone);
    }

    setLoading(false);
    setRefreshing(false);
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  function renderZone({ item }: { item: Zone }) {
    const reading = item.sensor_key ? latest[item.sensor_key] : undefined;
    const target = item.moisture_target ?? item.recommended_target ?? null;
    const value = reading?.value;
    const dry = value != null && target != null && value < target;
    return (
      <View style={styles.card}>
        <View style={styles.cardHeader}>
          <Text style={styles.zoneName}>{item.name}</Text>
          {item.sensor_key ? (
            <Text style={styles.sensorKey}>{item.sensor_key}</Text>
          ) : (
            <Text style={[styles.sensorKey, { color: '#bbb' }]}>no sensor</Text>
          )}
        </View>

        <View style={styles.moistureRow}>
          <Text style={[styles.moisture, dry && { color: '#c0392b' }]}>
            {value != null ? `${value.toFixed(0)}%` : '—'}
          </Text>
          <Text style={styles.target}>
            {target != null ? `target ${target.toFixed(0)}%` : 'no target'}
            {dry ? '  · dry' : value != null ? '  · ok' : ''}
          </Text>
        </View>

        <Text style={styles.crops}>
          {item.crops.length ? item.crops.join(', ') : 'No crops assigned'}
        </Text>
      </View>
    );
  }

  if (loading) {
    return <Loading />;
  }

  return (
    <View style={styles.container}>
      <View style={styles.topbar}>
        <View>
          <Text style={styles.title}>🌱 My garden</Text>
          {email ? <Text style={styles.email}>{email}</Text> : null}
        </View>
        <TouchableOpacity onPress={() => supabase.auth.signOut()}>
          <Text style={styles.signout}>Sign out</Text>
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
          <Text style={styles.empty}>
            No zones yet. Add your beds/containers in Setup (coming next), and the
            planner will place your crops into them.
          </Text>
        }
      />
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
  email: { color: '#999', fontSize: 12 },
  signout: { color: '#1a6faf', fontSize: 15 },
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
  moistureRow: { flexDirection: 'row', alignItems: 'baseline', gap: 10, marginVertical: 6 },
  moisture: { fontSize: 30, fontWeight: '800', color: '#3a7d44' },
  target: { fontSize: 13, color: '#888' },
  crops: { fontSize: 13, color: '#555' },
  empty: { textAlign: 'center', color: '#999', padding: 30, lineHeight: 20 },
});
