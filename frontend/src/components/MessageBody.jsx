import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import DiffView from "./DiffView.jsx";
import Collapsible from "./Collapsible.jsx";

const COLLAPSE_THRESHOLD = 500;

function RoleBadge({ role }) {
  const cls = role === "user" ? "role-user" : role === "assistant" ? "role-assistant" : "role-other";
  return <span className={`role-badge ${cls}`}>{role}</span>;
}

function Markdown({ text }) {
  return (
    <div className="msg-markdown">
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{text || ""}</ReactMarkdown>
    </div>
  );
}

function preview(text, n = 80) {
  const clean = (text || "").replace(/\s+/g, " ").trim();
  return clean.length > n ? clean.slice(0, n) + "…" : clean;
}

function toolResultText(content) {
  if (typeof content === "string") return content;
  if (Array.isArray(content)) {
    return content.map((b) => (typeof b === "string" ? b : b.text ?? JSON.stringify(b, null, 2))).join("\n");
  }
  return JSON.stringify(content, null, 2);
}

function ContentBlock({ block }) {
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
          <pre className="msg-code">{text}</pre>
        </Collapsible>
      );
    }

    case "tool_use": {
      const input = block.input || {};
      if (block.name === "Edit" && typeof input.old_string === "string") {
        return (
          <Collapsible variant="block" title={`Edit · ${input.file_path || "?"}`}>
            <DiffView bare before={input.old_string} after={input.new_string} />
          </Collapsible>
        );
      }
      if (block.name === "MultiEdit" && Array.isArray(input.edits)) {
        return (
          <Collapsible variant="block" title={`MultiEdit · ${input.file_path || "?"}`} meta={`${input.edits.length} edits`}>
            <div className="msg-blocks">
              {input.edits.map((e, i) => (
                <Collapsible key={i} variant="block" title={`Edit ${i + 1}/${input.edits.length}`}>
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
          <pre className="msg-code">{text}</pre>
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
          <pre className="msg-code">{text}</pre>
        </Collapsible>
      );
    }

    case "image":
      return <div className="msg-placeholder">[image]</div>;

    default: {
      const text = JSON.stringify(block, null, 2);
      return (
        <Collapsible
          variant="block"
          title={block.type || "content"}
          meta={preview(text, 60)}
          defaultOpen={text.length <= COLLAPSE_THRESHOLD}
        >
          <pre className="msg-code">{text}</pre>
        </Collapsible>
      );
    }
  }
}

function MessageContent({ content }) {
  if (content == null) return null;
  if (typeof content === "string" || Array.isArray(content)) {
    const blocks = typeof content === "string" ? [content] : content;
    return (
      <div className="msg-blocks">
        {blocks.map((b, i) => (
          <ContentBlock key={i} block={b} />
        ))}
      </div>
    );
  }
  const text = JSON.stringify(content, null, 2);
  return (
    <Collapsible variant="block" title="content" meta={preview(text, 60)} defaultOpen={text.length <= COLLAPSE_THRESHOLD}>
      <pre className="msg-code">{text}</pre>
    </Collapsible>
  );
}

function messageSummary(content) {
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

function metaValue(v) {
  const s = typeof v === "object" ? JSON.stringify(v) : String(v);
  return s.length > 160 ? s.slice(0, 160) + "…" : s;
}

export default function MessageBody({ raw }) {
  const [showRaw, setShowRaw] = useState(false);

  if (!raw) return <pre className="body-block">(empty)</pre>;

  let parsed = null;
  try {
    parsed = JSON.parse(raw);
  } catch {
    parsed = null;
  }

  const structured =
    parsed && typeof parsed === "object" && !Array.isArray(parsed) && (Array.isArray(parsed.messages) || Array.isArray(parsed.content));

  if (!structured) return <pre className="body-block">{raw}</pre>;

  const messages = Array.isArray(parsed.messages) ? parsed.messages : [{ role: parsed.role || "assistant", content: parsed.content }];
  const metaEntries = Object.entries(parsed).filter(([k]) => !["messages", "system", "content", "role"].includes(k));

  return (
    <div className="message-body">
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
        <div className="msg-meta">
          {metaEntries.map(([k, v]) => (
            <span className="msg-meta-item" key={k}>
              <strong>{k}</strong>: {metaValue(v)}
            </span>
          ))}
        </div>
      )}
      <button type="button" className="raw-toggle" onClick={() => setShowRaw((s) => !s)}>
        {showRaw ? "Hide raw JSON" : "Show raw JSON"}
      </button>
      {showRaw && <pre className="body-block">{raw}</pre>}
    </div>
  );
}
