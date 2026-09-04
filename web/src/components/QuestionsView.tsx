import { useState } from "react";

interface QuestionsViewProps {
  /** Called when a user picks a question; parent opens Discovery Chat with it. */
  onAsk: (question: string) => void;
}

interface QuestionGroup {
  id: string;
  title: string;
  icon: JSX.Element;
  questions: string[];
}

const QUESTION_GROUPS: QuestionGroup[] = [
  {
    id: "motivation",
    title: "Wishlist motivation",
    icon: (
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        <path d="M20.8 4.6a5.5 5.5 0 0 0-7.8 0L12 5.6l-1-1a5.5 5.5 0 1 0-7.8 7.8l1 1L12 21.2l7.8-7.8 1-1a5.5 5.5 0 0 0 0-7.8z" />
      </svg>
    ),
    questions: [
      "Why do users add fashion products to their wishlist?",
      "When do users use the wishlist as genuine purchase intent versus simply as a bookmarking mechanism?",
    ],
  },
  {
    id: "barriers",
    title: "Conversion barriers",
    icon: (
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="12" cy="12" r="9" />
        <path d="M5.6 5.6 18.4 18.4" />
      </svg>
    ),
    questions: [
      "What prevents wishlisted products from eventually being purchased?",
      "What causes users to postpone a purchase?",
      "What uncertainties remain after users have identified a product they like?",
    ],
  },
  {
    id: "journey",
    title: "Decision journey",
    icon: (
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        <path d="M4 18 9 8l4 5 3-4 4 9" />
      </svg>
    ),
    questions: [
      "How do users compare multiple shortlisted products?",
      "What information do users seek outside Myntra/AJIO before purchasing?",
      "What role do fit, size, styling, price, reviews, occasion and social validation play?",
    ],
  },
  {
    id: "needs",
    title: "Unmet needs",
    icon: (
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="9" cy="8" r="3" />
        <circle cx="17" cy="10" r="2.5" />
        <path d="M3.5 19a5.5 5.5 0 0 1 11 0" />
        <path d="M14.5 19a4 4 0 0 1 6 0" />
      </svg>
    ),
    questions: [
      "What unmet needs emerge consistently across user conversations?",
    ],
  },
];

export const EXPLORE_QUESTIONS: string[] = QUESTION_GROUPS.flatMap((group) => group.questions);

export default function QuestionsView({ onAsk }: QuestionsViewProps) {
  const [expanded, setExpanded] = useState(false);
  const [activeGroup, setActiveGroup] = useState<string>(QUESTION_GROUPS[0].id);

  const current = QUESTION_GROUPS.find((group) => group.id === activeGroup) ?? QUESTION_GROUPS[0];

  return (
    <section className="wi-ql-card" aria-label="Explore questions">
      <div className="wi-ql-card-head">
        <div className="wi-ql-card-title">
          <span className="wi-ql-card-icon" aria-hidden="true">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
              <path d="M21 12a8.5 8.5 0 0 1-8.5 8.5H8l-4 3V12A8.5 8.5 0 1 1 21 12Z" />
              <path d="M9.5 10a2.5 2.5 0 1 1 3.4 2.3c-.7.4-1.2.9-1.2 1.7" />
              <circle cx="12" cy="16.6" r="0.75" fill="currentColor" stroke="none" />
            </svg>
          </span>
          <div>
            <h3>Explore questions</h3>
            <p>Click one to open Discovery Chat</p>
          </div>
        </div>
        <button
          type="button"
          className="wi-ql-toggle"
          aria-expanded={expanded}
          onClick={() => setExpanded((open) => !open)}
        >
          {expanded ? "Hide" : "Show questions"}
        </button>
      </div>

      {expanded && (
        <div className="wi-ql-card-body">
          <div className="wi-ql-tabs" role="tablist" aria-label="Question categories">
            {QUESTION_GROUPS.map((group) => (
              <button
                key={group.id}
                type="button"
                role="tab"
                aria-selected={group.id === activeGroup}
                className={`wi-ql-tab ${group.id === activeGroup ? "active" : ""}`}
                onClick={() => setActiveGroup(group.id)}
              >
                <span className="wi-ql-tab-icon" aria-hidden="true">
                  {group.icon}
                </span>
                {group.title}
              </button>
            ))}
          </div>

          <div className="wi-ql-questions" role="tabpanel">
            {current.questions.map((question) => (
              <button
                key={question}
                type="button"
                className="wi-ql-chip"
                onClick={() => onAsk(question)}
                title="Ask Discovery Chat"
              >
                <span className="wi-ql-chip-text">{question}</span>
                <svg className="wi-ql-chip-icon" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                  <path d="M5 12h14M13 6l6 6-6 6" />
                </svg>
              </button>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}
