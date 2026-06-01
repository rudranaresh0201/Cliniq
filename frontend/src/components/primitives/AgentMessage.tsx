import React from 'react';
import { motion } from 'framer-motion';
import { agentMessage, staggerFast } from '../../lib/motion';

// ── Agent config ────────────────────────────────────────────────────────────

export type AgentType =
  | 'DeepDive'
  | 'CBC'
  | 'LFT'
  | 'RFT'
  | 'CrossAnalyzer'
  | 'WatchWorker'
  | 'MonitoringAgent'
  | 'EscalationAgent';

interface AgentMeta {
  color: string;
  label: string;
  icon: React.ReactElement;
}

// Inline SVG icons — Lucide-compatible 24 × 24 stroke style
const Icon = ({ path, path2 }: { path: string; path2?: string }) => (
  <svg
    width="14" height="14"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth={2}
    strokeLinecap="round"
    strokeLinejoin="round"
  >
    <path d={path} />
    {path2 && <path d={path2} />}
  </svg>
);

const AGENTS: Record<AgentType, AgentMeta> = {
  DeepDive: {
    color: '#7C65F6',
    label: 'DeepDive',
    icon: <Icon
      path="M12 2a4 4 0 0 1 4 4c0 1.5-.8 2.8-2 3.5V12h-4V9.5A4 4 0 0 1 12 2z"
      path2="M8 12H6a2 2 0 0 0-2 2v1a6 6 0 0 0 12 0v-1a2 2 0 0 0-2-2h-2"
    />,
  },
  CBC: {
    color: '#F87171',
    label: 'CBC',
    icon: <Icon path="M12 2.69l5.66 5.66a8 8 0 1 1-11.31 0z" />,
  },
  LFT: {
    color: '#FBBF24',
    label: 'LFT',
    icon: <Icon
      path="M9 3h6l-1 9H10L9 3z"
      path2="M6 21h12M7.5 12l-1.5 9h12l-1.5-9"
    />,
  },
  RFT: {
    color: '#2DD4BF',
    label: 'RFT',
    icon: <Icon path="M22 3H2l8 9.46V19l4 2v-8.54z" />,
  },
  CrossAnalyzer: {
    color: '#A78BFA',
    label: 'CrossAnalyzer',
    icon: <Icon
      path="M2 3h6l4 7 4-7h6M2 21h6l4-7 4 7h6"
    />,
  },
  WatchWorker: {
    color: '#60A5FA',
    label: 'WatchWorker',
    icon: <Icon
      path="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"
      path2="M12 9a3 3 0 1 0 0 6 3 3 0 0 0 0-6z"
    />,
  },
  MonitoringAgent: {
    color: '#34D399',
    label: 'MonitoringAgent',
    icon: <Icon path="M22 12h-4l-3 9L9 3l-3 9H2" />,
  },
  EscalationAgent: {
    color: '#FB923C',
    label: 'EscalationAgent',
    icon: <Icon
      path="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"
      path2="M12 9v4M12 17h.01"
    />,
  },
};

// ── Component ────────────────────────────────────────────────────────────────

export interface AgentMessageProps {
  agent: AgentType;
  action: string;
  finding: string;
  timestamp: string;
}

export function AgentMessage({ agent, action, finding, timestamp }: AgentMessageProps) {
  const meta = AGENTS[agent];

  return (
    <motion.div
      variants={agentMessage}
      style={{
        display: 'flex',
        alignItems: 'flex-start',
        gap: '10px',
      }}
    >
      {/* Icon circle */}
      <div
        style={{
          width: 28,
          height: 28,
          borderRadius: '50%',
          background: 'var(--bg-glass)',
          backdropFilter: 'blur(8px)',
          WebkitBackdropFilter: 'blur(8px)',
          border: `1px solid ${meta.color}33`,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          color: meta.color,
          flexShrink: 0,
          marginTop: '1px',
        }}
      >
        {meta.icon}
      </div>

      {/* Text */}
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: '6px', flexWrap: 'wrap' }}>
          <span
            style={{
              fontSize: '13px',
              fontWeight: 600,
              color: meta.color,
              letterSpacing: '0.1px',
              flexShrink: 0,
            }}
          >
            {meta.label}
          </span>
          <span
            style={{
              fontSize: '13px',
              color: 'var(--text-secondary)',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
            }}
          >
            {action}
          </span>
        </div>
        <p
          style={{
            margin: '2px 0 0',
            fontSize: '13px',
            color: 'var(--text-secondary)',
            lineHeight: 1.5,
          }}
        >
          {finding}
        </p>
        <time
          style={{
            display: 'block',
            marginTop: '3px',
            fontSize: '11px',
            color: 'var(--text-muted)',
            letterSpacing: '0.2px',
          }}
        >
          {timestamp}
        </time>
      </div>
    </motion.div>
  );
}

// ── Feed wrapper — use this to render a list with stagger ────────────────────

export function AgentFeed({ children }: { children: React.ReactNode }) {
  return (
    <motion.div
      variants={staggerFast}
      initial="hidden"
      animate="visible"
      style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}
    >
      {children}
    </motion.div>
  );
}
