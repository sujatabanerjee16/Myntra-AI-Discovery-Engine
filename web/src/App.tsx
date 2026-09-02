import { useEffect, useMemo, useState } from "react";
import "./App.css";
import AssistantView from "./components/AssistantView";
import DashboardView from "./components/DashboardView";
import { EXPLORE_QUESTIONS } from "./components/QuestionsView";
import {
  DEFAULT_SIDEBAR,
  EMPTY_FILTERS,
  type FilterState,
  type SidebarFilters,
} from "./types";

function MyntraMark() {
  return (
    <img
      className="myntra-mark"
      src="/myntra-logo.png"
      alt="Myntra"
      width={32}
      height={32}
    />
  );
}

function FashionBanner() {
  return (
    <div className="fashion-hero-banner">
      <div className="fashion-hero-glow fashion-hero-glow--pink" aria-hidden="true" />
      <div className="fashion-hero-glow fashion-hero-glow--violet" aria-hidden="true" />
      <div className="fashion-hero-grid" aria-hidden="true" />
      <div className="fashion-hero-content">
        <p className="fashion-hero-kicker">Myntra · Wishlist Intelligence</p>
        <h1>Wishlist Analytics</h1>
        <p className="fashion-hero-lead">
          Uncover why shoppers wait, what they want, and how to convert saved items into purchases.
        </p>
        <ul className="fashion-hero-highlights">
          <li>
            <strong>2 cohorts</strong>
            <span>Age 18–24 vs 25–35</span>
          </li>
          <li>
            <strong>Primary research</strong>
            <span>Wishlist + habits surveys</span>
          </li>
          <li>
            <strong>Grounded answers</strong>
            <span>Cited shopper evidence</span>
          </li>
          <li>
            <strong>PM calibration</strong>
            <span>Validate or flag a reason</span>
          </li>
        </ul>
      </div>
      <div className="fashion-hero-images" aria-hidden="true">
        <div className="fashion-hero-img-wrap">
          <img
            src="https://images.unsplash.com/photo-1483985988355-763728e1935b?auto=format&fit=crop&q=80&w=400&h=400"
            alt=""
          />
        </div>
        <div className="fashion-hero-img-wrap fashion-hero-img-wrap--large">
          <img
            src="https://images.unsplash.com/photo-1445205170230-053b83016050?auto=format&fit=crop&q=80&w=600&h=400"
            alt=""
          />
        </div>
        <div className="fashion-hero-img-wrap">
          <img
            src="https://images.unsplash.com/photo-1490481651871-ab68de25d43d?auto=format&fit=crop&q=80&w=400&h=400"
            alt=""
          />
        </div>
      </div>
    </div>
  );
}

export default function App() {
  const [filters, setFilters] = useState<FilterState>(EMPTY_FILTERS);
  const [sidebar, setSidebar] = useState<SidebarFilters>(DEFAULT_SIDEBAR);
  const [pendingQuestion, setPendingQuestion] = useState<string | undefined>(undefined);

  useEffect(() => {
    setSidebar((current) => {
      const sources = current.sources.filter((item) => item !== "research");
      const platforms = current.platforms.filter((item) => item !== "other");
      if (sources.length === current.sources.length && platforms.length === current.platforms.length) {
        return current;
      }
      return {
        ...current,
        sources: sources.length ? sources : DEFAULT_SIDEBAR.sources,
        platforms: platforms.length ? platforms : DEFAULT_SIDEBAR.platforms,
      };
    });
  }, []);

  const [activeNav, setActiveNav] = useState<"dashboard" | "competitive" | "chat">("dashboard");

  const [searchOpen, setSearchOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");

  const [notificationsOpen, setNotificationsOpen] = useState(false);
  const [notifications, setNotifications] = useState([
    {
      id: "eors-sync",
      title: "EORS Sync Complete",
      body: "Latest wishlist data imported successfully.",
      time: "2 mins ago",
      tone: "pink" as const,
      unread: true,
    },
    {
      id: "anomaly",
      title: "Anomaly Detected",
      body: "High price sensitivity in Footwear segment.",
      time: "1 hour ago",
      tone: "blue" as const,
      unread: true,
    },
  ]);
  const unreadCount = notifications.filter((item) => item.unread).length;

  const markAllNotificationsRead = () => {
    setNotifications((prev) => prev.map((item) => ({ ...item, unread: false })));
  };

  const [profileOpen, setProfileOpen] = useState(false);
  const [email, setEmail] = useState("analyst@myntra.com");
  const [isEditingEmail, setIsEditingEmail] = useState(false);
  const [draftEmail, setDraftEmail] = useState(email);

  const handleSaveEmail = (e: React.FormEvent) => {
    e.preventDefault();
    if (draftEmail.trim()) {
      setEmail(draftEmail.trim());
    }
    setIsEditingEmail(false);
  };

  const closeDropdowns = () => {
    setNotificationsOpen(false);
    setProfileOpen(false);
    setSearchOpen(false);
  };

  const goToDashboard = () => setActiveNav("dashboard");
  const goToCompetitive = () => setActiveNav("competitive");
  const goToChat = () => {
    setActiveNav("chat");
    window.setTimeout(() => {
      document
        .querySelector<HTMLInputElement>(".wi-chat-page .wi-chat-input input")
        ?.focus({ preventScroll: true });
    }, 60);
  };

  const handleAskQuestion = (question: string) => {
    setPendingQuestion(question);
    setActiveNav("chat");
  };

  const closeSearch = () => {
    setSearchOpen(false);
    setSearchQuery("");
  };

  const searchHits = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    const pages = [
      { id: "page-dashboard", label: "Dashboard", hint: "", run: goToDashboard },
      { id: "page-competitive", label: "Competitive Analysis", hint: "", run: goToCompetitive },
      { id: "page-chat", label: "Discovery Chat", hint: "", run: goToChat },
    ];
    const questions = EXPLORE_QUESTIONS.map((question) => ({
      id: `q-${question}`,
      label: question,
      hint: "Ask",
      run: () => handleAskQuestion(question),
    }));
    const pool = [...pages, ...questions];
    if (!q) return pages;
    return pool.filter((item) => item.label.toLowerCase().includes(q)).slice(0, 8);
  }, [searchQuery]);

  const runSearchHit = (hit: (typeof searchHits)[number]) => {
    hit.run();
    closeSearch();
  };

  const submitSearch = () => {
    const q = searchQuery.trim();
    if (searchHits.length) {
      runSearchHit(searchHits[0]);
      return;
    }
    if (q) {
      handleAskQuestion(q);
      closeSearch();
    }
  };

  return (
    <div className="app-shell" onClick={closeDropdowns}>
      <header className="app-topbar" onClick={(e) => e.stopPropagation()}>
        <div className="topbar-brand">
          <MyntraMark />
          <div className="brand-copy">
            <span className="brand-product">Wishlist Intelligence</span>
            <span className="brand-sub">Conversion discovery</span>
          </div>
        </div>

        <nav className="topbar-nav" aria-label="Primary">
          <button
            type="button"
            className={activeNav === "dashboard" ? "active" : ""}
            onClick={goToDashboard}
          >
            Dashboard
          </button>
          <button
            type="button"
            className={activeNav === "competitive" ? "active" : ""}
            onClick={goToCompetitive}
          >
            Competitive Analysis
          </button>
          <button
            type="button"
            className={activeNav === "chat" ? "active" : ""}
            onClick={goToChat}
          >
            Discovery Chat
          </button>
        </nav>

        <div className="topbar-actions relative">
          {searchOpen ? (
            <div className="topbar-search">
              <div className="topbar-search-bar">
                <svg
                  width="16"
                  height="16"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  className="search-icon-inside"
                >
                  <circle cx="11" cy="11" r="7" />
                  <path d="m21 21-4.3-4.3" />
                </svg>
                <input
                  type="search"
                  placeholder="Search pages or ask a question…"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  autoFocus
                  aria-label="Search"
                  onKeyDown={(e) => {
                    if (e.key === "Escape") closeSearch();
                    if (e.key === "Enter") {
                      e.preventDefault();
                      submitSearch();
                    }
                  }}
                />
                <button type="button" className="close-search" onClick={closeSearch} aria-label="Close search">
                  <svg
                    width="14"
                    height="14"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                  >
                    <path d="M18 6 6 18M6 6l12 12" />
                  </svg>
                </button>
              </div>
              <ul className="topbar-search-hits" role="listbox">
                {searchHits.map((hit) => (
                  <li key={hit.id}>
                    <button type="button" onClick={() => runSearchHit(hit)}>
                      <span>{hit.label}</span>
                      {hit.hint ? <em>{hit.hint}</em> : null}
                    </button>
                  </li>
                ))}
                {searchQuery.trim() && searchHits.length === 0 && (
                  <li>
                    <button type="button" onClick={submitSearch}>
                      <span>Ask “{searchQuery.trim()}”</span>
                      <em>Chat</em>
                    </button>
                  </li>
                )}
              </ul>
            </div>
          ) : (
            <button
              type="button"
              className="icon-btn"
              aria-label="Search"
              title="Search"
              onClick={() => {
                setSearchOpen(true);
                setNotificationsOpen(false);
                setProfileOpen(false);
              }}
            >
              <svg
                width="18"
                height="18"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <circle cx="11" cy="11" r="7" />
                <path d="m21 21-4.3-4.3" />
              </svg>
            </button>
          )}

          <div className="dropdown-container">
            <button
              type="button"
              className={`icon-btn ${notificationsOpen ? "active-icon" : ""}`}
              aria-label="Notifications"
              title="Notifications"
              onClick={() => {
                setNotificationsOpen(!notificationsOpen);
                setProfileOpen(false);
                setSearchOpen(false);
              }}
            >
              {unreadCount > 0 && <div className="notification-badge-dot" />}
              <svg
                width="18"
                height="18"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9" />
                <path d="M10.3 21a1.94 1.94 0 0 0 3.4 0" />
              </svg>
            </button>

            {notificationsOpen && (
              <div className="dropdown-menu notifications-menu">
                <div className="dropdown-header">
                  <h4>Notifications</h4>
                  <div className="dropdown-header-meta">
                    {unreadCount > 0 && (
                      <span className="notif-chip notif-chip--new">{unreadCount} new</span>
                    )}
                  </div>
                </div>
                <div className="notification-list">
                  {notifications.map((item) => (
                    <div
                      key={item.id}
                      className={`notification-item${item.unread ? " unread" : ""}`}
                    >
                      <div className={`notification-icon bg-${item.tone}`}>
                        {item.tone === "pink" ? (
                          <svg
                            width="14"
                            height="14"
                            viewBox="0 0 24 24"
                            fill="none"
                            stroke="white"
                            strokeWidth="2"
                            strokeLinecap="round"
                            strokeLinejoin="round"
                          >
                            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                            <polyline points="7 10 12 15 17 10" />
                            <line x1="12" y1="15" x2="12" y2="3" />
                          </svg>
                        ) : (
                          <svg
                            width="14"
                            height="14"
                            viewBox="0 0 24 24"
                            fill="none"
                            stroke="white"
                            strokeWidth="2"
                            strokeLinecap="round"
                            strokeLinejoin="round"
                          >
                            <circle cx="12" cy="12" r="10" />
                            <line x1="12" y1="8" x2="12" y2="12" />
                            <line x1="12" y1="16" x2="12.01" y2="16" />
                          </svg>
                        )}
                      </div>
                      <div className="notification-content">
                        <p>
                          <strong>{item.title}</strong>
                        </p>
                        <span>{item.body}</span>
                        <small>{item.time}</small>
                      </div>
                    </div>
                  ))}
                </div>
                <button
                  type="button"
                  className="dropdown-footer-btn"
                  onClick={markAllNotificationsRead}
                  disabled={unreadCount === 0}
                >
                  Mark all as read
                </button>
              </div>
            )}
          </div>

          <div className="dropdown-container">
            <button
              type="button"
              className={`icon-btn profile-btn ${profileOpen ? "active-icon border-pink" : ""}`}
              aria-label="Profile"
              title="Profile"
              onClick={() => {
                setProfileOpen(!profileOpen);
                setNotificationsOpen(false);
                setSearchOpen(false);
              }}
            >
              <svg
                width="18"
                height="18"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <circle cx="12" cy="8" r="4" />
                <path d="M4 20a8 8 0 0 1 16 0" />
              </svg>
            </button>

            {profileOpen && (
              <div className="dropdown-menu profile-menu">
                <div className="profile-header">
                  <div className="profile-avatar-large">{email.charAt(0).toUpperCase()}</div>
                  <div className="profile-info">
                    <strong>Myntra Analyst</strong>
                    <span className="profile-role">Admin</span>
                  </div>
                </div>

                <div className="profile-email-section">
                  <div className="email-label">Contact Email</div>
                  {isEditingEmail ? (
                    <form onSubmit={handleSaveEmail} className="email-edit-form">
                      <input
                        type="email"
                        value={draftEmail}
                        onChange={(e) => setDraftEmail(e.target.value)}
                        autoFocus
                        required
                      />
                      <div className="email-actions">
                        <button
                          type="button"
                          className="btn-cancel"
                          onClick={() => {
                            setIsEditingEmail(false);
                            setDraftEmail(email);
                          }}
                        >
                          Cancel
                        </button>
                        <button type="submit" className="btn-save">
                          Save
                        </button>
                      </div>
                    </form>
                  ) : (
                    <div className="email-display">
                      <span>{email}</span>
                      <button type="button" className="btn-edit" onClick={() => setIsEditingEmail(true)}>
                        <svg
                          width="12"
                          height="12"
                          viewBox="0 0 24 24"
                          fill="none"
                          stroke="currentColor"
                          strokeWidth="2"
                          strokeLinecap="round"
                          strokeLinejoin="round"
                        >
                          <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" />
                          <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" />
                        </svg>
                        Edit
                      </button>
                    </div>
                  )}
                </div>

                <div className="profile-menu-links">
                  <button type="button" disabled title="Coming soon" aria-disabled="true">
                    Account Settings
                  </button>
                  <button
                    type="button"
                    className="text-danger"
                    disabled
                    title="Coming soon"
                    aria-disabled="true"
                  >
                    Sign Out
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      </header>

      <div className="app-body">
      <FashionBanner />
      <main className={`app-main ${activeNav === "chat" ? "app-main--chat" : "app-main--unified"}`}>
        {/* Dashboard + Competitive share one data-driven view; kept mounted so
            switching tabs preserves loaded data and filter state. */}
        <div className="wi-tab-panel" hidden={activeNav === "chat"}>
          <DashboardView
            view={activeNav === "competitive" ? "competitive" : "dashboard"}
            filters={filters}
            onFiltersChange={setFilters}
            sidebar={sidebar}
            onSidebarChange={setSidebar}
            onAskQuestion={handleAskQuestion}
          />
        </div>

        {/* Discovery Chat stays mounted so conversation history survives tab switches. */}
        <div className="wi-tab-panel wi-chat-page" hidden={activeNav !== "chat"}>
          <AssistantView
            variant="page"
            platforms={sidebar.platforms}
            initialQuestion={pendingQuestion}
          />
        </div>
      </main>
      </div>
    </div>
  );
}
