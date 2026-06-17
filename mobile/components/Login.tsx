import { useState } from 'react';
import {
  ActivityIndicator,
  KeyboardAvoidingView,
  Platform,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from 'react-native';
import { supabase } from '../lib/supabase';

type Notice = { kind: 'info' | 'error'; text: string } | null;

function isUnconfirmed(error: any): boolean {
  return (
    error?.code === 'email_not_confirmed' ||
    /not confirmed|confirm your email/i.test(error?.message ?? '')
  );
}

export default function Login() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [notice, setNotice] = useState<Notice>(null);
  // Set when an account exists but its email isn't confirmed yet → show resend.
  const [unconfirmed, setUnconfirmed] = useState<string | null>(null);

  async function signIn() {
    setLoading(true);
    setNotice(null);
    setUnconfirmed(null);
    const { error } = await supabase.auth.signInWithPassword({ email, password });
    if (error) {
      if (isUnconfirmed(error)) {
        setUnconfirmed(email);
        setNotice({
          kind: 'info',
          text: `Your email isn't confirmed yet. Check ${email} (and spam) for the link, then sign in.`,
        });
      } else {
        setNotice({ kind: 'error', text: error.message });
      }
    }
    setLoading(false);
  }

  async function signUp() {
    setLoading(true);
    setNotice(null);
    setUnconfirmed(null);
    const { data, error } = await supabase.auth.signUp({ email, password });
    if (error) {
      setNotice({ kind: 'error', text: error.message });
    } else if (!data.session) {
      // No session means Supabase requires email confirmation first.
      setUnconfirmed(email);
      setNotice({
        kind: 'info',
        text: `We sent a confirmation link to ${email}. Tap it, then come back and sign in.`,
      });
    }
    // If a session WAS returned, App.tsx's auth listener navigates automatically.
    setLoading(false);
  }

  async function resend() {
    if (!unconfirmed) return;
    setLoading(true);
    const { error } = await supabase.auth.resend({ type: 'signup', email: unconfirmed });
    setNotice(
      error
        ? { kind: 'error', text: error.message }
        : { kind: 'info', text: `Confirmation link re-sent to ${unconfirmed}.` }
    );
    setLoading(false);
  }

  return (
    <KeyboardAvoidingView
      style={styles.container}
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}
    >
      <Text style={styles.logo}>🌱 thotamaali</Text>
      <Text style={styles.subtitle}>Your garden, watered.</Text>

      <TextInput
        style={styles.input}
        placeholder="Email"
        autoCapitalize="none"
        keyboardType="email-address"
        value={email}
        onChangeText={setEmail}
      />
      <TextInput
        style={styles.input}
        placeholder="Password"
        secureTextEntry
        value={password}
        onChangeText={setPassword}
      />

      {notice ? (
        <View
          style={[
            styles.notice,
            notice.kind === 'error' ? styles.noticeError : styles.noticeInfo,
          ]}
        >
          <Text
            style={notice.kind === 'error' ? styles.noticeErrorText : styles.noticeInfoText}
          >
            {notice.kind === 'info' ? '✉️  ' : '⚠️  '}
            {notice.text}
          </Text>
          {unconfirmed ? (
            <TouchableOpacity onPress={resend} disabled={loading}>
              <Text style={styles.resend}>Resend confirmation email</Text>
            </TouchableOpacity>
          ) : null}
        </View>
      ) : null}

      <TouchableOpacity style={styles.btn} onPress={signIn} disabled={loading}>
        {loading ? (
          <ActivityIndicator color="#fff" />
        ) : (
          <Text style={styles.btnText}>Sign in</Text>
        )}
      </TouchableOpacity>

      <TouchableOpacity onPress={signUp} disabled={loading}>
        <Text style={styles.link}>New here? Create an account</Text>
      </TouchableOpacity>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, justifyContent: 'center', padding: 24, backgroundColor: '#fcfcfa' },
  logo: { fontSize: 34, fontWeight: '800', textAlign: 'center', color: '#3a7d44' },
  subtitle: { textAlign: 'center', color: '#888', marginBottom: 28 },
  input: {
    borderWidth: 1, borderColor: '#ccc', borderRadius: 10, padding: 14,
    marginBottom: 12, fontSize: 16, backgroundColor: '#fff',
  },
  notice: { borderRadius: 10, padding: 12, marginBottom: 12 },
  noticeInfo: { backgroundColor: '#eef5ee', borderWidth: 1, borderColor: '#cfe3cf' },
  noticeError: { backgroundColor: '#fdecea', borderWidth: 1, borderColor: '#f5c6c0' },
  noticeInfoText: { color: '#2f6b3a', fontSize: 13, lineHeight: 18 },
  noticeErrorText: { color: '#c0392b', fontSize: 13, lineHeight: 18 },
  resend: { color: '#1a6faf', fontWeight: '700', marginTop: 8, fontSize: 13 },
  btn: {
    backgroundColor: '#3a7d44', borderRadius: 10, padding: 15,
    alignItems: 'center', marginTop: 4,
  },
  btnText: { color: '#fff', fontSize: 16, fontWeight: '700' },
  link: { textAlign: 'center', color: '#1a6faf', marginTop: 18, fontSize: 15 },
});
