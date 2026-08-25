import { useEffect, useMemo, useRef, useState } from "react";
import { askAssistant, getKeyQuestions } from "../api";
import type { AssistantAskResponse, Citation } from "../types";

type ChatMessage =
  | { role: "user"; text: string }
  | { role: "assistant"; response: AssistantAskResponse };

const FALLBACK_QUESTIONS = [
  "Why do users add fashion products to their wishlist?",
  "What prevents wishlisted products from eventually being purchased?",
  "Why do people wishlist on Myntra vs Nykaa or Ajio?",
  "Which wishlist motives are shared across platforms vs unique to Myntra?",
  "What uncertainties remain after users have identified a product they like?",
  "What causes users to postpone a purchase?",
  "How do users compare multiple shortlisted products?",
  "What information do users seek outside Myntra/AJIO before purchasing?",
  "What role do fit, size, styling, price, reviews, occasion and social validation play?",
  "When do users use the wishlist as genuine purchase intent versus simply as a bookmarking mechanism?",
  "How do these behaviors differ across user segments?",
  "What unmet needs emerge consistently across user conversations?",
];

function PlatformIcon({ platform }: { platform: string }) {
  const key = platform.toLowerCase();
  if (key.includes("play") || key.includes("playstore") || key.includes("play_store")) {
    return (
      <span className="platform-icon platform-icon--playstore" aria-hidden="true">
        <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor">
          <path d="M3.6 2.9 14.1 12 3.6 21.1c-.5-.3-.8-.8-.8-1.4V4.3c0-.6.3-1.1.8-1.4z" opacity="0.95" />
          <path d="M14.1 12 17.7 8.9l3.1-1.8c.7-.4.7-1.1 0-1.5L14.1 12z" opacity="0.75" />
          <path d="M14.1 12 17.7 15.1l3.1 1.8c.7.4.7 1.1 0 1.5L14.1 12z" opacity="0.85" />
          <path d="m14.1 12-10.5 9.1 10.2-5.9L17.7 15 14.1 12z" opacity="0.7" />
        </svg>
      </span>
    );
  }
  if (key.includes("internal") || key.includes("user data")) {
    return (
      <span className="platform-icon platform-icon--internal" aria-hidden="true">
        <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
          <ellipse cx="12" cy="6" rx="7" ry="3" />
          <path d="M5 6v6c0 1.7 3.1 3 7 3s7-1.3 7-3V6" />
          <path d="M5 12v6c0 1.7 3.1 3 7 3s7-1.3 7-3v-6" />
        </svg>
      </span>
    );
  }
  if (key.includes("reddit")) {
    return (
      <span className="platform-icon platform-icon--reddit" aria-hidden="true">
        <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor">
          <circle cx="12" cy="12" r="10" opacity="0.15" />
          <circle cx="9" cy="12" r="1.4" />
          <circle cx="15" cy="12" r="1.4" />
          <path d="M8.5 15.2c1 .9 2.2 1.3 3.5 1.3s2.5-.4 3.5-1.3" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
          <circle cx="17.5" cy="8" r="1.2" />
          <path d="M14.2 9.2 16.5 8" fill="none" stroke="currentColor" strokeWidth="1.2" />
        </svg>
      </span>
    );
  }
  if (key.includes("youtube")) {
    return (
      <span className="platform-icon platform-icon--youtube" aria-hidden="true">
        <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor">
          <rect x="3" y="6" width="18" height="12" rx="3" opacity="0.2" />
          <path d="M10 9.5v5l5-2.5-5-2.5z" />
        </svg>
      </span>
    );
  }
  if (key.includes("instagram")) {
    return (
      <span className="platform-icon platform-icon--instagram" aria-hidden="true">
        <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="1.8">
          <rect x="4" y="4" width="16" height="16" rx="4" />
          <circle cx="12" cy="12" r="3.5" />
          <circle cx="16.5" cy="7.5" r="1" fill="currentColor" stroke="none" />
        </svg>
      </span>
    );
  }
  return <span className="platform-icon platform-icon--generic" aria-hidden="true">◆</span>;
}

function citationLabel(citation: Citation, index: number): string {
  const source = citation.source || "Source";
  const short = source.replace(/_/g, " ");
  return `${short} #${index + 1}`;
}

function inferTags(citation: Citation): string[] {
  const tags: string[] = [];
  const hay = `${citation.source} ${citation.excerpt}`.toLowerCase();
  if (hay.includes("price") || hay.includes("cost") || hay.includes("expensive")) tags.push("Price Sensitivity");
  if (hay.includes("size") || hay.includes("fit") || hay.includes("sizing")) tags.push("Sizing Issues");
  if (hay.includes("quality") || hay.includes("fabric") || hay.includes("material")) tags.push("Product Quality");
  if (hay.includes("footwear") || hay.includes("shoe") || hay.includes("sneaker")) tags.push("Footwear");
  if (hay.includes("apparel") || hay.includes("dress") || hay.includes("cloth")) tags.push("Apparel");
  if (hay.includes("fit") && !tags.includes("Sizing Issues")) tags.push("Fit");
  return tags.slice(0, 2);
}

/** Split merged survey/chat excerpts into readable Q/A or sentence blocks. */
function formatEvidenceExcerpt(excerpt: string): { kind: "qa" | "text"; question?: string; answer?: string; text?: string }[] {
  const cleaned = excerpt.replace(/\s+/g, " ").trim();
  if (!cleaned) return [];

  const hasQa = /(?:^|\s)Q\s*[:.]/i.test(cleaned) && /(?:^|\s)A\s*[:.]/i.test(cleaned);

  if (hasQa) {
    const segments = cleaned
      .replace(/(?:^|\s)(Q\s*[:.]?\s*\d*[.)]?)/gi, "\n$1")
      .replace(/(?:\s)(A\s*[:.])/gi, "\n$1")
      .split("\n")
      .map((line) => line.trim())
      .filter(Boolean);

    const blocks: { kind: "qa"; question: string; answer: string }[] = [];
    let currentQ = "";

    for (const segment of segments) {
      if (/^Q\s*[:.]?\s*\d*/i.test(segment)) {
        if (currentQ) {
          blocks.push({ kind: "qa", question: currentQ, answer: "" });
        }
        currentQ = segment.replace(/^Q\s*[:.]?\s*\d*[.)]?\s*/i, "").trim() || segment;
      } else if (/^A\s*[:.]/i.test(segment)) {
        const answer = segment.replace(/^A\s*[:.]\s*/i, "").trim();
        blocks.push({ kind: "qa", question: currentQ, answer });
        currentQ = "";
      } else if (currentQ) {
        currentQ = `${currentQ} ${segment}`.trim();
      } else {
        blocks.push({ kind: "qa", question: "", answer: segment });
      }
    }
    if (currentQ) {
      blocks.push({ kind: "qa", question: currentQ, answer: "" });
    }
    if (blocks.length > 0) return blocks;
  }

  const sentences = cleaned
    .split(/(?<=[.!?])\s+(?=[A-Z“"])/)
    .map((s) => s.trim())
    .filter(Boolean);

  if (sentences.length > 1) {
    return sentences.map((text) => ({ kind: "text" as const, text }));
  }

  return [{ kind: "text", text: cleaned }];
}

function EvidenceExcerpt({ excerpt }: { excerpt: string }) {
  const blocks = formatEvidenceExcerpt(excerpt);
  return (
    <div className="wi-evidence-excerpt">
      {blocks.map((block, index) =>
        block.kind === "qa" ? (
          <div key={index} className="wi-evidence-qa">
            {block.question ? (
              <p className="wi-evidence-q">
                <span className="wi-evidence-label">Q</span>
                <span>{block.question}</span>
              </p>
            ) : null}
            {block.answer ? (
              <p className="wi-evidence-a">
                <span className="wi-evidence-label wi-evidence-label--a">A</span>
                <span>{block.answer}</span>
              </p>
            ) : null}
          </div>
        ) : (
          <p key={index} className="wi-evidence-line">
            {block.text}
          </p>
        ),
      )}
    </div>
  );
}

function AiAvatar() {
  return (
    <div className="ai-avatar" aria-hidden="true">
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
        <rect x="5" y="7" width="14" height="10" rx="3" />
        <path d="M9 11h.01M15 11h.01M10 14h4" strokeLinecap="round" />
        <path d="M12 4v3M8 4l1.5 3M16 4l-1.5 3" strokeLinecap="round" />
      </svg>
    </div>
  );
}

interface AssistantViewProps {
  variant?: "page" | "widget" | "panel";
  onClose?: () => void;
  /** Competitor platforms (myntra/nykaa/ajio/other) from the shared filter rail. */
  platforms?: string[];
  /** Whether the shared "Social" source is selected, to tune suggested questions. */
  socialSelected?: boolean;
  /** A question to auto-run on mount (e.g. picked from the Explore Questions tab). */
  initialQuestion?: string;
}

export default function AssistantView({
  variant = "page",
  onClose,
  platforms,
  socialSelected = false,
  initialQuestion,
}: AssistantViewProps) {
  const isWidget = variant === "widget";
  const isPanel = variant === "panel";
  const isCompact = isWidget || isPanel;
  const [questions, setQuestions] = useState<string[]>(FALLBACK_QUESTIONS);
  const [draft, setDraft] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [evidenceOpen, setEvidenceOpen] = useState(!isCompact);
  const [showAllSuggestions, setShowAllSuggestions] = useState(false);
  const chatEndRef = useRef<HTMLDivElement>(null);
  const autoAskedRef = useRef<string | null>(null);

  useEffect(() => {
    const decorate = (base: string[]) =>
      socialSelected
        ? [
            "What styling debates or sizing questions do users bring to Reddit?",
            "How do influencer reviews or visual hauls address sizing uncertainties?",
            ...base.slice(0, 8),
          ]
        : base;

    void getKeyQuestions()
      .then((items) => {
        setQuestions(decorate(items.length ? items : FALLBACK_QUESTIONS));
      })
      .catch(() => {
        setQuestions(decorate(FALLBACK_QUESTIONS));
      });
  }, [socialSelected]);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  const latestCitations = useMemo(() => {
    for (let i = messages.length - 1; i >= 0; i -= 1) {
      const msg = messages[i];
      if (msg.role === "assistant" && msg.response.citations.length > 0) {
        return msg.response.citations;
      }
    }
    return [];
  }, [messages]);

  const suggested = questions;
  const askedTexts = useMemo(
    () => new Set(messages.filter((m): m is { role: "user"; text: string } => m.role === "user").map((m) => m.text)),
    [messages],
  );
  const followUps = useMemo(
    () => suggested.filter((item) => !askedTexts.has(item)),
    [suggested, askedTexts],
  );

  const submit = async (text: string) => {
    const trimmed = text.trim();
    if (!trimmed || loading) return;
    setDraft("");
    setMessages((prev) => [...prev, { role: "user", text: trimmed }]);
    setLoading(true);
    setError(null);
    setEvidenceOpen(true);
    try {
      // Scope the answer to the platforms selected in the shared filter rail.
      const response = await askAssistant(trimmed, platforms);
      setMessages((prev) => [...prev, { role: "assistant", response }]);
    } catch (err) {
      setError(String(err));
    } finally {
      setLoading(false);
    }
  };

  // Auto-run a question passed in from the Explore Questions tab. The ref guard
  // keeps React 18 StrictMode's double effect invocation from asking twice.
  useEffect(() => {
    const q = initialQuestion?.trim();
    if (q && autoAskedRef.current !== q) {
      autoAskedRef.current = q;
      void submit(q);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialQuestion]);

  const renderAnswerText = (response: AssistantAskResponse) => {
    const confidencePct = Math.round(response.confidence * 100);
    return (
      <div className="wi-answer-content">
        <div className="wi-answer-text">
          {response.answer.split('\n').map((paragraph, i) => (
            <p key={i}>{paragraph}</p>
          ))}
        </div>
        
        <div className="wi-answer-footer">
          <div className="wi-citations-group">
            {response.citations.map((citation, index) => (
              <button
                key={citation.chunk_id}
                type="button"
                className="citation-chip"
                onClick={() => setEvidenceOpen(true)}
                title={citation.excerpt}
              >
                [{citationLabel(citation, index)}]
              </button>
            ))}
          </div>
          <strong className="confidence-inline">Confidence: {confidencePct}%</strong>
        </div>
      </div>
    );
  };

  return (
    <div
      className={`wi-assistant wi-assistant--nofilter ${evidenceOpen ? "" : "wi-assistant--no-evidence"} ${
        isWidget ? "wi-assistant--widget" : ""
      } ${isPanel ? "wi-assistant--panel" : ""}`}
    >
      <section className="wi-chat-panel">
        <div className="wi-chat-header">
          <div className="wi-chat-header-row">
            <div className="wi-chat-title-group">
              <h2>Discovery Chat</h2>
              <p className="wi-chat-purpose">
                Ask questions in everyday language and get answers backed by real shopper
                feedback — no dashboards or filters needed.
              </p>
            </div>
            <div className="wi-chat-header-actions">
              <button
                type="button"
                className="wi-chat-tool-btn"
                onClick={() => setEvidenceOpen((open) => !open)}
              >
                {evidenceOpen ? "Hide evidence" : "Evidence"}
              </button>
              {onClose && (
                <button type="button" className="icon-btn" aria-label="Close assistant" onClick={onClose}>
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
                    <path d="M18 6 6 18M6 6l12 12" />
                  </svg>
                </button>
              )}
            </div>
          </div>
        </div>

        <div className="wi-chat-messages">
          {messages.length === 0 && !loading && (
            <div className="wi-chat-empty">
              <div className="wi-welcome">
                <div className="wi-welcome-icon" aria-hidden="true">
                  <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M12 3 13.9 8.6 19.5 8.6 15 12.1 16.6 17.6 12 14.2 7.4 17.6 9 12.1 4.5 8.6 10.1 8.6z" />
                  </svg>
                </div>
                <h3 className="wi-welcome-title">Not sure where to start? Just ask.</h3>
                <p className="wi-welcome-sub">
                  I turn thousands of shopper conversations into clear answers about wishlist
                  behavior. Every answer cites its sources and shows a confidence score.
                </p>
              </div>

              <section className="wi-explore-questions" aria-label="Explore Questions">
                <div className="wi-explore-questions-head">
                  <h3 className="wi-explore-questions-title">Explore Questions</h3>
                  <p className="wi-explore-questions-sub">
                    Ready-made questions answered from real shopper feedback. Click any one for an
                    instant, evidence-backed answer.
                  </p>
                </div>
                <div className="wi-explore-questions-chips">
                  {(showAllSuggestions ? suggested : suggested.slice(0, 6)).map((item) => (
                    <button
                      key={item}
                      type="button"
                      className="wi-followup-chip"
                      onClick={() => void submit(item)}
                      title={item}
                    >
                      {item}
                    </button>
                  ))}
                </div>
                {suggested.length > 6 && (
                  <button
                    type="button"
                    className="wi-suggested-more"
                    onClick={() => setShowAllSuggestions((open) => !open)}
                  >
                    {showAllSuggestions ? "Show fewer" : `Show ${suggested.length - 6} more`}
                  </button>
                )}
              </section>
            </div>
          )}

          {messages.map((msg, index) =>
            msg.role === "user" ? (
              <div key={`u-${index}`} className="wi-bubble wi-bubble--user">
                {msg.text}
              </div>
            ) : (
              <div key={`a-${index}`} className="wi-bubble-row">
                <AiAvatar />
                <div className="wi-bubble wi-bubble--assistant">
                  {renderAnswerText(msg.response)}
                  {msg.response.insufficient_evidence && (
                    <div className="wi-low-evidence">Low evidence — treat this answer cautiously.</div>
                  )}
                  {msg.response.limitations && (
                    <div className="wi-limitations">
                      <div className="wi-limitations-header">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                          <circle cx="12" cy="12" r="10"></circle>
                          <line x1="12" y1="8" x2="12" y2="12"></line>
                          <line x1="12" y1="16" x2="12.01" y2="16"></line>
                        </svg>
                        <strong>Limitations</strong>
                      </div>
                      <p>{msg.response.limitations}</p>
                    </div>
                  )}
                </div>
              </div>
            ),
          )}

          {loading && (
            <div className="wi-bubble-row">
              <AiAvatar />
              <div className="wi-bubble wi-bubble--assistant wi-bubble--loading">
                <span className="typing-dot" />
                <span className="typing-dot" />
                <span className="typing-dot" />
              </div>
            </div>
          )}

          {error && <div className="error-banner">{error}</div>}

          {messages.length > 0 && !loading && followUps.length > 0 && (
            <div className="wi-followups" role="list" aria-label="Explore more questions">
              <div className="wi-followups-label">Explore more questions</div>
              <div className="wi-followups-chips">
                {(showAllSuggestions ? followUps : followUps.slice(0, 4)).map((item) => (
                  <button
                    key={item}
                    type="button"
                    role="listitem"
                    className="wi-followup-chip"
                    onClick={() => void submit(item)}
                    title={item}
                  >
                    {item}
                  </button>
                ))}
              </div>
              {followUps.length > 4 && (
                <button
                  type="button"
                  className="wi-suggested-more"
                  onClick={() => setShowAllSuggestions((open) => !open)}
                >
                  {showAllSuggestions ? "Show fewer" : `Show ${followUps.length - 4} more`}
                </button>
              )}
            </div>
          )}

          <div ref={chatEndRef} />
        </div>

        <div className="wi-chat-input-wrap">
          <form
            className="wi-chat-input"
            onSubmit={(e) => {
              e.preventDefault();
              void submit(draft);
            }}
          >
            <input
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              placeholder="Ask anything about wishlist data..."
              disabled={loading}
              aria-label="Ask Discovery Chat"
            />
            <button type="submit" disabled={loading || !draft.trim()} aria-label="Send">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
                <path d="M2.01 21 23 12 2.01 3 2 10l15 2-15 2z" />
              </svg>
            </button>
          </form>
          {messages.length === 0 && (
            <p className="wi-chat-input-hint">
              e.g. “Compare why people wishlist sneakers on Myntra vs Ajio”
            </p>
          )}
        </div>
      </section>

      {evidenceOpen && (
        <aside className="wi-evidence-drawer">
          <div className="wi-evidence-header">
            <h2>Evidence Drawer</h2>
            <button type="button" className="icon-btn dark" aria-label="Close evidence" onClick={() => setEvidenceOpen(false)}>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
                <path d="M18 6 6 18M6 6l12 12" />
              </svg>
            </button>
          </div>

          <div className="wi-evidence-list">
            {latestCitations.length === 0 ? (
              <p className="wi-evidence-empty muted">
                Citations from the latest answer will appear here.
              </p>
            ) : (
              latestCitations.map((citation, index) => {
                const tags = inferTags(citation);
                return (
                  <article key={citation.chunk_id} className="wi-evidence-card">
                    <div className="wi-evidence-card-head">
                      <PlatformIcon platform={citation.source} />
                      <div>
                        <div className="wi-evidence-source">
                          Source: {citation.source.replace(/_/g, " ")}
                        </div>
                        <div className="wi-evidence-meta">
                          {citationLabel(citation, index)} · score {Math.round(citation.score * 100)}%
                        </div>
                      </div>
                    </div>
                    <EvidenceExcerpt excerpt={citation.excerpt} />
                    {tags.length > 0 && (
                      <div className="wi-evidence-tags">
                        {tags.map((tag) => (
                          <span key={tag} className="wi-tag">
                            [Tag: {tag}]
                          </span>
                        ))}
                      </div>
                    )}
                  </article>
                );
              })
            )}
          </div>
        </aside>
      )}
    </div>
  );
}
