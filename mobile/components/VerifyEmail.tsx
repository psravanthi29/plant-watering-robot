import { useEffect, useRef, useState } from 'react';
import { ActivityIndicator, StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import { supabase } from '../lib/supabase';

// A dedicated, full-screen "verify your email" step. This takes over the whole
// screen after sign-up (or when sign-in fails because the email isn't confirmed)
// so the verification step is impossible to miss — the previous inline notice was
// easy to scroll past while the sign-in form still looked interactive.
const RESEND_COOLDOWN_S = 30;

export default function VerifyEmail({
  email,
  onBack,
}: {
  email: string;
  onBack: () => void;
}) {
  const [loading, setLoading] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [cooldown, setCooldown] = useState(0);
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);

  // Tick the resend cooldown down to zero.
  useEffect(() => {
    if (cooldown <= 0) return;
    timer.current = setInterval(() => setCooldown((c) => Math.max(0, c - 1)), 1000);
    return () => {
      if (timer.current) clearInterval(timer.current);
    };
  }, [cooldown]);

  async function resend() {
    if (cooldown > 0 || loading) return;
    setLoading(true);
    setNotice(null);
    const { error } = await supabase.auth.resend({ type: 'signup', email });
    if (error) {
      setNotice(error.message);
    } else {
      setNotice(`Confirmation link re-sent to ${email}.`);
      setCooldown(RESEND_COOLDOWN_S);
    }
    setLoading(false);
  }

  return (
    <View style={styles.container}>
      <Text style={styles.icon}>✉️</Text>
      <Text style={styles.title}>Check your email</Text>
      <Text style={styles.body}>
        We sent a confirmation link to{'\n'}
        <Text style={styles.email}>{email}</Text>
      </Text>
      <Text style={styles.hint}>
        Tap the link to verify your account, then come back here and sign in. The
        link can take a minute to arrive — check your spam folder too.
      </Text>

      {notice ? <Text style={styles.notice}>{notice}</Text> : null}

      <TouchableOpacity
        style={[styles.btn, (cooldown > 0 || loading) && styles.btnDisabled]}
        onPress={resend}
        disabled={cooldown > 0 || loading}
      >
        {loading ? (
          <ActivityIndicator color="#fff" />
        ) : (
          <Text style={styles.btnText}>
            {cooldown > 0 ? `Resend in ${cooldown}s` : 'Resend confirmation email'}
          </Text>
        )}
      </TouchableOpacity>

      <TouchableOpacity onPress={onBack}>
        <Text style={styles.link}>I've verified — back to sign in</Text>
      </TouchableOpacity>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, justifyContent: 'center', padding: 28, backgroundColor: '#fcfcfa' },
  icon: { fontSize: 56, textAlign: 'center', marginBottom: 8 },
  title: { fontSize: 26, fontWeight: '800', textAlign: 'center', color: '#3a7d44' },
  body: { textAlign: 'center', color: '#555', fontSize: 16, lineHeight: 24, marginTop: 12 },
  email: { fontWeight: '800', color: '#222' },
  hint: { textAlign: 'center', color: '#888', fontSize: 13, lineHeight: 19, marginTop: 14 },
  notice: { textAlign: 'center', color: '#2f6b3a', fontSize: 13, marginTop: 18 },
  btn: {
    backgroundColor: '#3a7d44', borderRadius: 10, padding: 15,
    alignItems: 'center', marginTop: 26,
  },
  btnDisabled: { backgroundColor: '#a9c6ae' },
  btnText: { color: '#fff', fontSize: 16, fontWeight: '700' },
  link: { textAlign: 'center', color: '#1a6faf', marginTop: 20, fontSize: 15 },
});
