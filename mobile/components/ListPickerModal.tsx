import {
  FlatList,
  Modal,
  Pressable,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from 'react-native';

export type PickerOption = { key: string; label: string; sublabel?: string };

// Generic bottom-sheet list picker — dep-free (no native picker). Used to add a
// crop from the library and to reassign a crop's zone.
export default function ListPickerModal({
  visible,
  title,
  options,
  onPick,
  onClose,
  emptyText,
}: {
  visible: boolean;
  title: string;
  options: PickerOption[];
  onPick: (key: string) => void;
  onClose: () => void;
  emptyText?: string;
}) {
  return (
    <Modal visible={visible} animationType="slide" transparent onRequestClose={onClose}>
      <Pressable style={styles.backdrop} onPress={onClose}>
        <Pressable style={styles.sheet} onPress={(e) => e.stopPropagation()}>
          <Text style={styles.title}>{title}</Text>
          <FlatList
            data={options}
            keyExtractor={(o) => o.key}
            style={{ maxHeight: 420 }}
            ListEmptyComponent={
              <Text style={styles.empty}>{emptyText ?? 'Nothing to choose from.'}</Text>
            }
            renderItem={({ item }) => (
              <TouchableOpacity style={styles.row} onPress={() => onPick(item.key)}>
                <Text style={styles.rowLabel}>{item.label}</Text>
                {item.sublabel ? <Text style={styles.rowSub}>{item.sublabel}</Text> : null}
              </TouchableOpacity>
            )}
          />
          <TouchableOpacity onPress={onClose}>
            <Text style={styles.cancel}>Cancel</Text>
          </TouchableOpacity>
        </Pressable>
      </Pressable>
    </Modal>
  );
}

const styles = StyleSheet.create({
  backdrop: { flex: 1, backgroundColor: 'rgba(0,0,0,0.35)', justifyContent: 'flex-end' },
  sheet: {
    backgroundColor: '#fcfcfa', borderTopLeftRadius: 18, borderTopRightRadius: 18,
    padding: 20, paddingBottom: 34, maxHeight: '85%',
  },
  title: { fontSize: 20, fontWeight: '800', color: '#222', marginBottom: 10 },
  row: { paddingVertical: 14, borderBottomWidth: 1, borderBottomColor: '#eee' },
  rowLabel: { fontSize: 16, color: '#222' },
  rowSub: { fontSize: 12, color: '#999', marginTop: 2 },
  empty: { color: '#999', textAlign: 'center', padding: 24 },
  cancel: { textAlign: 'center', color: '#888', marginTop: 16, fontSize: 15 },
});
