import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import DiffView from "./DiffView";
import Collapsible from "./Collapsible";
import { useUiStore } from "../store/uiStore";

const COLLAPSE_THRESHOLD = 500;

const BODY_BLOCK = "rounded-lg border border-border bg-panel p-4 overflow-x-auto text-[0.8rem] whitespace-pre-wrap break-words";
const MSG_CODE = "m-0 text-[0.78rem] whitespace-pre-wrap break-words max-h-80 overflow-y-auto";

const ROLE_TONES = {
  user: "bg-accent/14 text-accent",
  assistant: "bg-ok/14 text-ok",
  other: "bg-muted/14 text-muted",
};

const PROSE =
  "prose prose-sm prose-invert max-w-none text-[0.85rem] leading-relaxed " +
  "prose-headings:text-text prose-headings:font-medium " +
  "prose-a:text-accent prose-a:no-underline hover:prose-a:underline " +
  "prose-strong:text-text " +
  "prose-code:text-text prose-code:bg-bg prose-code:border prose-code:border-border prose-code:rounded prose-code:px-1.5 prose-code:py-0.5 prose-code:before:content-none prose-code:after:content-none " +
  "prose-pre:bg-bg prose-pre:border prose-pre:border-border " +
  "prose-blockquote:border-l-border prose-blockquote:text-muted prose-blockquote:font-normal " +
  "prose-hr:border-border " +
  "prose-th:border prose-th:border-border prose-td:border prose-td:border-border";

// Message bodies are arbitrary, provider-shaped JSON — this describes the
// superset of fields we know how to render, not a strict discriminated union.
interface ContentBlockData {
  type?: string;
  text?: string;
  thinking?: string;
  name?: string;
  input?: Record<string, unknown>;
  content?: unknown;
  is_error?: boolean;
}

type MessageContentValue = string | ContentBlockData[] | Record<string, unknown> | null | undefined;

interface ParsedMessage {
  role?: string;
  content?: MessageContentValue;
}

interface ParsedBody {
  messages?: ParsedMessage[];
  system?: MessageContentValue;
  content?: MessageContentValue;
  role?: string;
  [key: string]: unknown;
}

interface EditInput {
  old_string?: string;
  new_string?: string;
  file_path?: string;
}

interface MultiEditEdit {
  old_string?: string;
  new_string?: string;
}

interface MultiEditInput {
  file_path?: string;
  edits?: MultiEditEdit[];
}

function RoleBadge({ role }: { role: string }) {
  const tone = role === "user" ? ROLE_TONES.user : role === "assistant" ? ROLE_TONES.assistant : ROLE_TONES.other;
  return (
    <span className={`inline-block rounded-full px-2.5 py-0.5 text-[0.7rem] font-semibold uppercase tracking-wide ${tone}`}>{role}</span>
  );
}

function Markdown({ text }: { text: string | null | undefined }) {
  return (
    <div className={PROSE}>
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{text || ""}</ReactMarkdown>
    </div>
  );
}

function preview(text: string | null | undefined, n = 80) {
  const clean = (text || "").replace(/\s+/g, " ").trim();
  return clean.length > n ? clean.slice(0, n) + "…" : clean;
}

function toolResultText(content: unknown): string {
  if (typeof content === "string") return content;
  if (Array.isArray(content)) {
    return content
      .map((b) => (typeof b === "string" ? b : ((b as { text?: string })?.text ?? JSON.stringify(b, null, 2))))
      .join("\n");
  }
  return JSON.stringify(content, null, 2);
}

function ContentBlock({ block }: { block: string | ContentBlockData }) {
  if (typeof block === "string") {
    return (
      <Collapsible variant="block" title="text" meta={preview(block)} defaultOpen={block.length <= COLLAPSE_THRESHOLD}>
        <Markdown text={block} />
      </Collapsible>
    );
  }

  switch (block.type) {
    case "text":
      return (
        <Collapsible
          variant="block"
          title="text"
          meta={preview(block.text)}
          defaultOpen={(block.text || "").length <= COLLAPSE_THRESHOLD}
        >
          <Markdown text={block.text} />
        </Collapsible>
      );

    case "thinking": {
      const text = block.thinking || "";
      return (
        <Collapsible variant="block" title="thinking" meta={preview(text)} defaultOpen={text.length <= COLLAPSE_THRESHOLD}>
          <pre className={MSG_CODE}>{text}</pre>
        </Collapsible>
      );
    }

    case "tool_use": {
      const input = block.input || {};
      if (block.name === "Edit" && typeof input.old_string === "string") {
        const editInput = input as unknown as EditInput;
        return (
          <Collapsible variant="block" title={`Edit · ${editInput.file_path || "?"}`}>
            <DiffView bare before={editInput.old_string} after={editInput.new_string} />
          </Collapsible>
        );
      }
      if (block.name === "MultiEdit" && Array.isArray(input.edits)) {
        const multiInput = input as unknown as MultiEditInput;
        const edits = multiInput.edits ?? [];
        return (
          <Collapsible variant="block" title={`MultiEdit · ${multiInput.file_path || "?"}`} meta={`${edits.length} edits`}>
            <div className="flex flex-col gap-2.5">
              {edits.map((e, i) => (
                <Collapsible key={i} variant="block" title={`Edit ${i + 1}/${edits.length}`}>
                  <DiffView bare before={e.old_string} after={e.new_string} />
                </Collapsible>
              ))}
            </div>
          </Collapsible>
        );
      }
      const text = JSON.stringify(input, null, 2);
      return (
        <Collapsible
          variant="block"
          title={`tool_use · ${block.name}`}
          meta={preview(text, 60)}
          defaultOpen={text.length <= COLLAPSE_THRESHOLD}
        >
          <pre className={MSG_CODE}>{text}</pre>
        </Collapsible>
      );
    }

    case "tool_result": {
      const text = toolResultText(block.content);
      return (
        <Collapsible
          variant="block"
          tone={block.is_error ? "err" : undefined}
          title={`tool_result${block.is_error ? " · error" : ""}`}
          meta={preview(text, 60)}
          defaultOpen={text.length <= COLLAPSE_THRESHOLD}
        >
          <pre className={MSG_CODE}>{text}</pre>
        </Collapsible>
      );
    }

    case "image":
      return <div className="text-[0.8rem] italic text-muted">[image]</div>;

    default: {
      const text = JSON.stringify(block, null, 2);
      return (
        <Collapsible
          variant="block"
          title={block.type || "content"}
          meta={preview(text, 60)}
          defaultOpen={text.length <= COLLAPSE_THRESHOLD}
        >
          <pre className={MSG_CODE}>{text}</pre>
        </Collapsible>
      );
    }
  }
}

function MessageContent({ content }: { content: MessageContentValue }) {
  if (content == null) return null;
  if (typeof content === "string" || Array.isArray(content)) {
    const blocks: (string | ContentBlockData)[] = typeof content === "string" ? [content] : content;
    return (
      <div className="flex flex-col gap-2.5">
        {blocks.map((b, i) => (
          <ContentBlock key={i} block={b} />
        ))}
      </div>
    );
  }
  const text = JSON.stringify(content, null, 2);
  return (
    <Collapsible variant="block" title="content" meta={preview(text, 60)} defaultOpen={text.length <= COLLAPSE_THRESHOLD}>
      <pre className={MSG_CODE}>{text}</pre>
    </Collapsible>
  );
}

function messageSummary(content: MessageContentValue): string {
  if (typeof content === "string") return preview(content, 100);
  if (Array.isArray(content)) {
    const firstText = content.find((b) => typeof b === "string" || b.type === "text");
    if (firstText) return preview(typeof firstText === "string" ? firstText : firstText.text, 100);
    const toolNames = content.filter((b) => b && b.type === "tool_use").map((b) => b.name);
    if (toolNames.length) return toolNames.join(", ");
    return content.map((b) => (typeof b === "string" ? "text" : b.type)).join(", ");
  }
  return "";
}

function metaValue(v: unknown): string {
  const s = typeof v === "object" ? JSON.stringify(v) : String(v);
  return s.length > 160 ? s.slice(0, 160) + "…" : s;
}

interface MessageBodyProps {
  raw: string | null | undefined;
  bodyKey: string;
}

export default function MessageBody({ raw, bodyKey }: MessageBodyProps) {
  const showRaw = useUiStore((s) => s.showRawByKey[bodyKey] ?? false);
  const toggleShowRaw = useUiStore((s) => s.toggleShowRaw);

  if (!raw) return <pre className={BODY_BLOCK}>(empty)</pre>;

  let parsed: ParsedBody | null = null;
  try {
    parsed = JSON.parse(raw);
  } catch {
    parsed = null;
  }

  const structured =
    parsed && typeof parsed === "object" && !Array.isArray(parsed) && (Array.isArray(parsed.messages) || Array.isArray(parsed.content));

  if (!structured || !parsed) return <pre className={BODY_BLOCK}>{raw}</pre>;

  const messages = Array.isArray(parsed.messages) ? parsed.messages : [{ role: parsed.role || "assistant", content: parsed.content }];
  const metaEntries = Object.entries(parsed).filter(([k]) => !["messages", "system", "content", "role"].includes(k));

  return (
    <div className="flex flex-col gap-3">
      {parsed.system && (
        <Collapsible variant="card" title={<RoleBadge role="system" />} meta={messageSummary(parsed.system)}>
          <MessageContent content={parsed.system} />
        </Collapsible>
      )}
      {messages.map((m, i) => (
        <Collapsible key={i} variant="card" title={<RoleBadge role={m.role || "?"} />} meta={messageSummary(m.content)}>
          <MessageContent content={m.content} />
        </Collapsible>
      ))}
      {metaEntries.length > 0 && (
        <div className="flex flex-wrap gap-x-4 gap-y-1.5 text-xs text-muted">
          {metaEntries.map(([k, v]) => (
            <span key={k}>
              <strong className="font-medium text-text">{k}</strong>: {metaValue(v)}
            </span>
          ))}
        </div>
      )}
      <button
        type="button"
        className="self-start rounded-md border border-border px-2.5 py-1.5 text-xs text-muted hover:border-accent hover:text-text"
        onClick={() => toggleShowRaw(bodyKey)}
      >
        {showRaw ? "Hide raw JSON" : "Show raw JSON"}
      </button>
      {showRaw && <pre className={BODY_BLOCK}>{raw}</pre>}
    </div>
  );
}
