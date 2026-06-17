import { useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import Dashboard from './Dashboard';
import Setup from './Setup';
import Planner from './Planner';

type Tab = 'garden' | 'setup' | 'planner';

const TABS: { key: Tab; label: string; icon: string }[] = [
  { key: 'garden', label: 'Garden', icon: '🌱' },
  { key: 'setup', label: 'Setup', icon: '🪴' },
  { key: 'planner', label: 'Planner', icon: '📋' },
];

// Lightweight state-based tab shell — no navigation lib needed, identical on web
// and native. Each tab keeps its own data-loading; switching tabs is instant and
// the screens refetch on mount / pull-to-refresh.
export default function Main({ email }: { email?: string }) {
  const [tab, setTab] = useState<Tab>('garden');

  return (
    <View style={styles.root}>
      <View style={styles.screen}>
        {tab === 'garden' && <Dashboard email={email} />}
        {tab === 'setup' && <Setup />}
        {tab === 'planner' && <Planner />}
      </View>

      <View style={styles.tabbar}>
        {TABS.map((t) => {
          const active = t.key === tab;
          return (
            <Pressable key={t.key} style={styles.tab} onPress={() => setTab(t.key)}>
              <Text style={[styles.tabIcon, !active && styles.tabInactive]}>{t.icon}</Text>
              <Text style={[styles.tabLabel, active ? styles.tabActiveLabel : styles.tabInactive]}>
                {t.label}
              </Text>
            </Pressable>
          );
        })}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: '#fcfcfa' },
  screen: { flex: 1 },
  tabbar: {
    flexDirection: 'row',
    borderTopWidth: 1,
    borderTopColor: '#eee',
    backgroundColor: '#fff',
    paddingBottom: 18,
    paddingTop: 8,
  },
  tab: { flex: 1, alignItems: 'center', justifyContent: 'center', gap: 2 },
  tabIcon: { fontSize: 20 },
  tabLabel: { fontSize: 11, fontWeight: '700' },
  tabActiveLabel: { color: '#3a7d44' },
  tabInactive: { opacity: 0.45 },
});
