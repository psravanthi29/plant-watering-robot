import { StyleSheet, Text, View } from 'react-native';

// Placeholder for the next milestone: pick crops, call GET /api/placement to
// auto-suggest a zone for each (with override), then POST /api/placement/apply.
export default function Planner() {
  return (
    <View style={styles.container}>
      <View style={styles.topbar}>
        <Text style={styles.title}>📋 Planner</Text>
      </View>
      <View style={styles.body}>
        <Text style={styles.emoji}>🌾</Text>
        <Text style={styles.heading}>Crop planning is coming next</Text>
        <Text style={styles.text}>
          Here you'll pick the crops you want to grow, and the app will auto-suggest
          which zone each one goes in — grouping them by water need so a single valve
          can serve the whole zone. You'll be able to override any placement.
        </Text>
        <Text style={styles.text}>
          First, add your beds and containers in the Setup tab.
        </Text>
      </View>
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
  body: { flex: 1, justifyContent: 'center', alignItems: 'center', padding: 34 },
  emoji: { fontSize: 44, marginBottom: 16 },
  heading: { fontSize: 18, fontWeight: '700', color: '#444', marginBottom: 10, textAlign: 'center' },
  text: { fontSize: 14, color: '#888', textAlign: 'center', lineHeight: 21, marginBottom: 12 },
});
