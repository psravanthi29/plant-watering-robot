import { useCallback, useEffect, useState } from 'react';
import {
  Image,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from 'react-native';
import { apiFetch, captureUrl } from '../lib/api';
import Loading from './Loading';
import ListPickerModal, { PickerOption } from './ListPickerModal';

type VisionLog = {
  id: number;
  timestamp: string;
  zone: string;
  image_count: number | null;
  source: string | null;
  analysis: string | null;
};
type Session = {
  timestamp: string;
  analysis: string | null;
  source: string | null;
  image_paths: string[];
};
type Zone = { id: number; name: string; sensor_key?: string | null };

function friendlyError(err: any): string {
  const msg = err?.message ?? String(err);
  if (/failed to fetch|network request failed|did not respond/i.test(msg)) {
    return 'Could not reach the server — it may be waking up. Pull to refresh in a few seconds.';
  }
  if (/API 401/.test(msg)) return 'Session expired. Pull to refresh or sign in again.';
  return msg;
}

// Plant-health view — read-only for now (photo capture is deferred). Shows the
// AI vision log, and a per-zone photo timeline with an "analyze progress" trend.
// Photos are uploaded via the existing web page until in-app capture lands.
export default function Health() {
  const [logs, setLogs] = useState<VisionLog[]>([]);
  const [zones, setZones] = useState<Zone[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Per-zone timeline state.
  const [zonePickOpen, setZonePickOpen] = useState(false);
  const [activeZone, setActiveZone] = useState<string | null>(null);
  const [sessions, setSessions] = useState<Session[]>([]);
  const [sessionsLoading, setSessionsLoading] = useState(false);
  const [progress, setProgress] = useState<string | null>(null);
  const [progressBusy, setProgressBusy] = useState(false);

  const load = useCallback(async () => {
    setError(null);
    const [logRes, zoneRes] = await Promise.allSettled([
      apiFetch<VisionLog[]>('/api/vision/logs'),
      apiFetch<Zone[]>('/api/zones'),
    ]);
    // The vision endpoints are new; if they aren't deployed yet just show empty
    // state rather than a scary error. Only a zones failure is worth surfacing.
    setLogs(logRes.status === 'fulfilled' ? logRes.value : []);
    if (zoneRes.status === 'fulfilled') setZones(zoneRes.value);
    else setError(friendlyError(zoneRes.reason));
    setLoading(false);
    setRefreshing(false);
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const loadSessions = useCallback(async (zone: string) => {
    setSessionsLoading(true);
    setProgress(null);
    try {
      const res = await apiFetch<{ zone: string; sessions: Session[] }>(
        `/api/vision/sessions?zone=${encodeURIComponent(zone)}`
      );
      // Newest first for display.
      setSessions([...res.sessions].reverse());
    } catch (e) {
      setError(friendlyError(e));
    } finally {
      setSessionsLoading(false);
    }
  }, []);

  function pickZone(zoneKey: string) {
    setZonePickOpen(false);
    setActiveZone(zoneKey);
    loadSessions(zoneKey);
  }

  async function analyzeProgress() {
    if (!activeZone) return;
    setProgressBusy(true);
    setError(null);
    try {
      const res = await apiFetch<{ analysis: string }>('/api/vision/progress', {
        method: 'POST',
        body: JSON.stringify({ zone: activeZone }),
      });
      setProgress(res.analysis);
      await loadSessions(activeZone); // a progress run is also logged
    } catch (e) {
      setError(friendlyError(e));
    } finally {
      setProgressBusy(false);
    }
  }

  if (loading) return <Loading />;

  const zoneOptions: PickerOption[] = zones.map((z) => ({
    key: z.sensor_key || z.name,
    label: z.name,
    sublabel: z.sensor_key ?? 'no sensor key',
  }));

  return (
    <View style={styles.container}>
      <View style={styles.topbar}>
        <Text style={styles.title}>📷 Plant health</Text>
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

        <Text style={styles.note}>
          📸 In-app photo capture is coming soon. For now, upload photos from the
          web dashboard; their AI analysis appears here.
        </Text>

        {/* Per-zone progress timeline */}
        <Text style={styles.section}>Progress timeline</Text>
        <TouchableOpacity style={styles.zonePick} onPress={() => setZonePickOpen(true)}>
          <Text style={styles.zonePickText}>
            {activeZone ? `Zone: ${activeZone}` : 'Pick a zone to view its photos'}
          </Text>
          <Text style={styles.zoneChange}>{activeZone ? 'Change' : 'Pick'}</Text>
        </TouchableOpacity>

        {activeZone ? (
          sessionsLoading ? (
            <Text style={styles.muted}>Loading…</Text>
          ) : sessions.length === 0 ? (
            <Text style={styles.muted}>No photos captured for this zone yet.</Text>
          ) : (
            <>
              <TouchableOpacity
                style={styles.progressBtn}
                onPress={analyzeProgress}
                disabled={progressBusy}
              >
                <Text style={styles.progressBtnText}>
                  {progressBusy ? 'Comparing photos…' : '🔬 Analyze progress over time'}
                </Text>
              </TouchableOpacity>
              {progress ? (
                <View style={styles.progressBox}>
                  <Text style={styles.progressLabel}>Progress assessment</Text>
                  <Text style={styles.analysisText}>{progress}</Text>
                </View>
              ) : null}

              {sessions.map((s, i) => (
                <View key={i} style={styles.sessionCard}>
                  <Text style={styles.sessionDate}>
                    {s.timestamp.slice(0, 16).replace('T', ' ')}{' '}
                    <Text style={styles.muted}>({s.source})</Text>
                  </Text>
                  {s.image_paths.length ? (
                    <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.thumbs}>
                      {s.image_paths.map((p, j) => (
                        <Image key={j} source={{ uri: captureUrl(p) }} style={styles.thumb} />
                      ))}
                    </ScrollView>
                  ) : null}
                  {s.analysis ? <Text style={styles.analysisText}>{s.analysis}</Text> : null}
                </View>
              ))}
            </>
          )
        ) : null}

        {/* Vision log across all zones */}
        <Text style={styles.section}>Recent analyses</Text>
        {logs.length === 0 ? (
          <Text style={styles.muted}>No analyses yet.</Text>
        ) : (
          logs.map((l) => (
            <View key={l.id} style={styles.logCard}>
              <Text style={styles.logHead}>
                <Text style={styles.bold}>{l.zone}</Text> ·{' '}
                {l.timestamp.slice(0, 16).replace('T', ' ')} ·{' '}
                <Text style={styles.muted}>{l.source}</Text>
              </Text>
              {l.analysis ? (
                <Text style={styles.analysisText} numberOfLines={6}>
                  {l.analysis}
                </Text>
              ) : null}
            </View>
          ))
        )}
      </ScrollView>

      <ListPickerModal
        visible={zonePickOpen}
        title="Pick a zone"
        options={zoneOptions}
        onPick={pickZone}
        onClose={() => setZonePickOpen(false)}
        emptyText="No zones yet — add one in Setup."
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#fcfcfa' },
  topbar: {
    paddingTop: 56, paddingHorizontal: 18, paddingBottom: 12,
    borderBottomWidth: 1, borderBottomColor: '#eee', backgroundColor: '#fff',
  },
  title: { fontSize: 22, fontWeight: '800', color: '#222' },
  errorBox: { backgroundColor: '#fdecea', padding: 12, borderRadius: 10, marginBottom: 10 },
  error: { color: '#c0392b', fontSize: 13 },
  note: {
    backgroundColor: '#f4f8f4', borderLeftWidth: 3, borderLeftColor: '#3a7d44',
    padding: 12, borderRadius: 8, color: '#456', fontSize: 13, lineHeight: 19,
  },
  section: { fontSize: 15, fontWeight: '800', color: '#444', marginTop: 22, marginBottom: 8 },
  muted: { color: '#999', fontSize: 13, paddingVertical: 4 },
  bold: { fontWeight: '700', color: '#222' },
  zonePick: {
    flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center',
    backgroundColor: '#fff', borderWidth: 1, borderColor: '#ececec', borderRadius: 10,
    padding: 14,
  },
  zonePickText: { fontSize: 14, color: '#444' },
  zoneChange: { fontSize: 14, color: '#1a6faf', fontWeight: '700' },
  progressBtn: {
    backgroundColor: '#f0ecfa', borderWidth: 1, borderColor: '#d8cdf0',
    borderRadius: 10, padding: 13, alignItems: 'center', marginTop: 10,
  },
  progressBtnText: { color: '#6a4caf', fontWeight: '700', fontSize: 14 },
  progressBox: {
    backgroundColor: '#f7f4fc', borderLeftWidth: 4, borderLeftColor: '#6a4caf',
    borderRadius: 8, padding: 12, marginTop: 10,
  },
  progressLabel: { fontWeight: '800', color: '#6a4caf', marginBottom: 4, fontSize: 13 },
  sessionCard: {
    backgroundColor: '#fff', borderRadius: 12, padding: 14, marginTop: 10,
    borderWidth: 1, borderColor: '#ececec',
  },
  sessionDate: { fontWeight: '700', color: '#3a7d44', fontSize: 14 },
  thumbs: { marginVertical: 8 },
  thumb: {
    width: 110, height: 110, borderRadius: 8, marginRight: 8,
    backgroundColor: '#eee', borderWidth: 1, borderColor: '#ddd',
  },
  analysisText: { fontSize: 13, color: '#555', lineHeight: 19, marginTop: 4 },
  logCard: {
    backgroundColor: '#fff', borderRadius: 12, padding: 14, marginBottom: 8,
    borderWidth: 1, borderColor: '#ececec',
  },
  logHead: { fontSize: 13, color: '#555' },
});
