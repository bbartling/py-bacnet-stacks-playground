import CodeMirror from "@uiw/react-codemirror";
import { python } from "@codemirror/lang-python";
import { oneDark } from "@codemirror/theme-one-dark";
import { EditorView } from "@codemirror/view";
import { useMemo } from "react";
import { useTheme } from "../contexts/theme-context";

const lightEditorTheme = EditorView.theme(
  {
    "&": {
      backgroundColor: "#ffffff",
      color: "#111827",
    },
    ".cm-content": {
      caretColor: "#2f57c7",
    },
    ".cm-cursor, .cm-dropCursor": {
      borderLeftColor: "#2f57c7",
    },
    "&.cm-focused .cm-selectionBackground, .cm-selectionBackground, .cm-content ::selection": {
      backgroundColor: "#d8e4ff !important",
    },
    ".cm-gutters": {
      backgroundColor: "#f6f8fc",
      color: "#556179",
      borderRight: "1px solid #d8dfec",
    },
    ".cm-activeLineGutter": {
      backgroundColor: "#eef2fa",
    },
    ".cm-activeLine": {
      backgroundColor: "#f4f7fc",
    },
    ".cm-line": {
      padding: "0 2px",
    },
  },
  { dark: false },
);

type Props = {
  value: string;
  onChange: (value: string) => void;
  height?: string;
  readOnly?: boolean;
};

export function PythonCodeEditor({ value, onChange, height = "220px", readOnly }: Props) {
  const { theme } = useTheme();
  const extensions = useMemo(
    () => [python(), theme === "dark" ? oneDark : lightEditorTheme],
    [theme],
  );

  return (
    <CodeMirror
      value={value}
      height={height}
      theme={theme === "dark" ? "dark" : "light"}
      extensions={extensions}
      readOnly={readOnly}
      onChange={onChange}
      basicSetup={{
        lineNumbers: true,
        foldGutter: true,
        highlightActiveLine: true,
      }}
    />
  );
}
