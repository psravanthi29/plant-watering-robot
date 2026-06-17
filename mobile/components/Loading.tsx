import { useEffect, useState } from 'react';
import { ActivityIndicator, StyleSheet, Text, View } from 'react-native';

// Full-screen spinner that, after a few seconds, explains the likely cold-start
// delay — so a slow first request reads as "waking up" rather than a hang.
export default function Loading() {
  const [slow, setSlow] = useState(false);

  useEffect(() => {
    const t = setTimeout(() => setSlow(true), 4000);
    return () => clearTimeout(t);
  }, []);

  return (
    <View style={styles.center}>
      <ActivityIndicator size="large" color="#3a7d44" />
      {slow ? (
        <Text style={styles.hint}>
          Waking up the server… the free tier sleeps when idle, so the first load
          after a while can take a minute or two.
        </Text>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  center: { flex: 1, justifyContent: 'center', alignItems: 'center', padding: 34 },
  hint: { marginTop: 18, color: '#999', textAlign: 'center', lineHeight: 20, fontSize: 13 },
});
