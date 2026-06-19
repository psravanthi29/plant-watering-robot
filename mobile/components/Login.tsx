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
import VerifyEmail from './VerifyEmail';

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
  // When set, an account exists but its email isn't confirmed → take over the
  // whole screen with a dedicated "check your email" step (see VerifyEmail).
  const [pendingEmail, setPendingEmail] = useState<string | null>(null);

  async function signIn() {
    setLoading(true);
    setNotice(null);
    const { error } = await supabase.auth.signInWithPassword({ email, password });
    if (error) {
      if (isUnconfirmed(error)) {
        setPendingEmail(email);
      } else {
        setNotice({ kind: 'error', text: error.message });
      }
    }
    setLoading(false);
  }

  async function signUp() {
    setLoading(true);
    setNotice(null);
    const { data, error } = await supabase.auth.signUp({ email, password });
    if (error) {
      setNotice({ kind: 'error', text: error.message });
    } else if (!data.session) {
      // No session means Supabase requires email confirmation first → show the
      // dedicated verify-your-email screen so the step can't be missed.
      setPendingEmail(email);
    }
    // If a session WAS returned, App.tsx's auth listener navigates automatically.
    setLoading(false);
  }

  if (pendingEmail) {
    return <VerifyEmail email={pendingEmail} onBack={() => setPendingEmail(null)} />;
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
  btn: {
    backgroundColor: '#3a7d44', borderRadius: 10, padding: 15,
    alignItems: 'center', marginTop: 4,
  },
  btnText: { color: '#fff', fontSize: 16, fontWeight: '700' },
  link: { textAlign: 'center', color: '#1a6faf', marginTop: 18, fontSize: 15 },
});
