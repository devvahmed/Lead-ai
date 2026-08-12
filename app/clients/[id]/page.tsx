'use client';

import { useState, useEffect, use, useRef, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import Link from 'next/link';
import { getAuthToken, getSavedCompany } from '@/lib/auth';


interface Client {
  id: string;
  name: string;
  website: string;
  industry: string;
  country: string;
  trust_score: number;
  relevance_reason: string;
  status: string;
  email?: string;
  phone?: string;
  logo_url?: string;
  created_at: string;
  contact_source_context?: string; // Stage 2 JSON stored here
  linkedin_company?: string;
  contact_source_url?: string;
  contact_source_label?: string;
  phones?: string;
  matched_service?: string;
  match_reason?: string;
  search_query?: string | null;
}

interface EmailHistoryEntry {
  id: number;
  client_id: number;
  company_id: number;
  email_type: 'outreach' | 'followup' | 'negotiation';
  label: string;
  subject?: string;
  body: string;
  recipient_email?: string;
  status: string;
  created_at: string;
}

interface ContactMeta {
  email: string;
  source_url?: string;
  source_page?: string;
  source_context?: string;
  source_label?: string;
}

interface ContactData {
  primary_email: string | null;
  all_emails: string[];
  email_meta: ContactMeta[];
  phones: string[];
  linkedin_company: string | null;
  linkedin_people: string[];
  contact_page_url: string | null;
  source_label: string;
  source_context: string;
  stakeholder?: string;
  context_snippet?: string;
  outreach_suggestion?: string;
  found: boolean;
  loading: boolean;
}

const tabs = ['Overview', 'Contact Info', 'Outreach Email', 'Email History'];

const STATUS_STYLES: Record<string, string> = {
  Qualified:           'bg-[#e8f5e9] text-[#2e7d32] border-[#c8e6c9]',
  'Awaiting Outreach': 'bg-[#fff8e1] text-[#f57f17] border-[#ffe082]',
  Contacted:           'bg-[#e3f2fd] text-[#1565c0] border-[#90caf9]',
  Cold:                'bg-[#ffebee] text-[#c62828] border-[#ef9a9a]',
  Pending:             'bg-yellow-100 text-yellow-800 border-yellow-200',
};

const LOGO_COLORS = [
  'bg-[#08478a]', 'bg-[#2e7d32]', 'bg-[#1565c0]',
  'bg-[#6a1b9a]', 'bg-[#00695c]', 'bg-[#c62828]',
];

function getTrustLabel(score: number) {
  if (score >= 85) return 'High Intent';
  if (score >= 70) return 'Good Fit';
  if (score >= 50) return 'Moderate';
  return 'Low Intent';
}

function getDomain(url: string): string {
  try { return new URL(url.startsWith('http') ? url : `https://${url}`).hostname.replace(/^www\./, ''); }
  catch { return url; }
}

function getCleanPageName(urlOrPath?: string | null): string {
  if (!urlOrPath) return 'Homepage';
  try {
    let clean = urlOrPath.replace(/^SOURCE_URL:\s*/i, '').trim();
    if (clean.startsWith('http')) {
      clean = new URL(clean).pathname;
    }
    clean = clean.replace(/\/+$/, '');
    if (!clean || clean === '') return 'Homepage';
    const lower = clean.toLowerCase();
    if (lower.includes('contact')) return 'Contact Page';
    if (lower.includes('about')) return 'About Page';
    if (lower.includes('team')) return 'Team Page';
    return clean.startsWith('/') ? clean : `/${clean}`;
  } catch {
    return 'Website Page';
  }
}

// ─── Copy Button ──────────────────────────────────────────────────────────────
function CopyBtn({ value }: { value: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      onClick={() => { navigator.clipboard.writeText(value); setCopied(true); setTimeout(() => setCopied(false), 2000); }}
      className={`flex items-center gap-1 px-2 py-0.5 rounded-lg text-[11px] font-semibold transition-all flex-shrink-0 ${
        copied ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500 hover:bg-blue-50 hover:text-blue-600'
      }`}
    >
      <span className="material-symbols-outlined text-[12px]">{copied ? 'check' : 'content_copy'}</span>
      {copied ? 'Copied!' : 'Copy'}
    </button>
  );
}

// ─── Single contact row ───────────────────────────────────────────────────────
function ContactItem({ icon, label, value, href, iconColor }: {
  icon: string; label: string; value: string; href?: string; iconColor?: string;
}) {
  return (
    <div className="flex items-center justify-between py-3 border-b border-gray-100 last:border-0 gap-3">
      <div className="flex items-center gap-2.5 min-w-0">
        <span className={`material-symbols-outlined text-[18px] flex-shrink-0 ${iconColor || 'text-gray-400'}`}>{icon}</span>
        <span className="text-[13px] text-gray-500 whitespace-nowrap">{label}</span>
      </div>
      <div className="flex items-center gap-2 min-w-0">
        {href ? (
          <a href={href} target="_blank" rel="noreferrer"
            className="text-[13px] font-semibold text-blue-600 hover:underline truncate max-w-[220px]">
            {value}
          </a>
        ) : (
          <span className="text-[13px] font-semibold text-gray-800 truncate max-w-[220px]">{value}</span>
        )}
        <CopyBtn value={value} />
      </div>
    </div>
  );
}

const DEFAULT_TASKS = [
  { label: 'Initial AI Analysis', done: false },
  { label: 'Outbound Email Sent', done: false },
  { label: 'Schedule Demo Call', done: false },
  { label: 'Prepare Custom Proposal', done: false },
];

// ─── Main Page ────────────────────────────────────────────────────────────────
export default function ClientDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [client, setClient]   = useState<Client | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState('Overview');
  const [tasks, setTasks]     = useState(DEFAULT_TASKS);
  const [contacts, setContacts] = useState<ContactData>({
    primary_email: null,
    all_emails: [],
    email_meta: [],
    phones: [],
    linkedin_company: null,
    linkedin_people: [],
    contact_page_url: null,
    source_label: 'Contact Page',
    source_context: '',
    found: false,
    loading: false,
  });
  // Stage 2 polling state: 'idle' | 'polling' | 'done' | 'timeout'
  const [stage2State, setStage2State] = useState<'idle' | 'polling' | 'done' | 'timeout'>('idle');
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const pollCountRef = useRef(0);

  // Outreach Email Generation & Sending State
  const [emailSubject, setEmailSubject] = useState('');
  const [emailBody, setEmailBody] = useState('');
  const [emailGenerating, setEmailGenerating] = useState(false);
  const [emailError, setEmailError] = useState<string | null>(null);
  const [emailCopied, setEmailCopied] = useState(false);
  const [pitchType, setPitchType] = useState<'targeted' | 'general'>('general');
  const [customKeyword, setCustomKeyword] = useState('');

  const [sendingEmail, setSendingEmail] = useState(false);
  const [sendSuccess, setSendSuccess] = useState<string | null>(null);
  const [sendError, setSendError] = useState<string | null>(null);

  const [ourCompanyName, setOurCompanyName] = useState('WTechX');
  const [ourServices, setOurServices] = useState('AI, Robotics, and Computer Vision solutions');

  useEffect(() => {
    const saved = getSavedCompany();
    if (saved) {
      setOurCompanyName(saved.name || 'WTechX');
      if (saved.services || saved.description) {
        setOurServices(saved.services || saved.description || 'AI & B2B Solutions');
      }
    }
  }, []);

  // Email History State
  const [emailHistory, setEmailHistory] = useState<EmailHistoryEntry[]>([]);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [selectedHistoryEmail, setSelectedHistoryEmail] = useState<EmailHistoryEntry | null>(null);
  const [historyCopied, setHistoryCopied] = useState(false);

  const autoSaveToHistory = useCallback(async (type: 'outreach' | 'followup' | 'negotiation', subj: string, bodyText: string) => {
    if (!client) return;
    try {
      const token = getAuthToken();
      const res = await fetch(`/api/clients/${client.id}/email-history`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({
          email_type: type,
          subject: subj,
          body: bodyText,
          recipient_email: contacts.primary_email || client.email || null,
          status: 'Draft',
        }),
      });
      const data = await res.json();
      if (res.ok && data.email) {
        setEmailHistory(prev => [data.email, ...prev]);
      }
    } catch (err) {
      console.warn('[Auto Save Email History Error]', err);
    }
  }, [client, contacts.primary_email]);

  const fetchEmailHistory = useCallback(async () => {
    if (!client) return;
    setLoadingHistory(true);
    try {
      const token = getAuthToken();
      const res = await fetch(`/api/clients/${client.id}/email-history`, {
        headers: token ? { 'Authorization': `Bearer ${token}` } : {},
      });
      const data = await res.json();
      if (res.ok && data.history) {
        setEmailHistory(data.history);
      }
    } catch (err) {
      console.warn('[Fetch Email History Error]', err);
    } finally {
      setLoadingHistory(false);
    }
  }, [client]);

  useEffect(() => {
    if (activeTab === 'Email History' && client) {
      fetchEmailHistory();
    }
  }, [activeTab, client, fetchEmailHistory]);

  const handleSendEmail = useCallback(async () => {
    if (!client || !emailBody || !contacts.primary_email) return;
    setSendingEmail(true);
    setSendError(null);
    setSendSuccess(null);

    try {
      const res = await fetch('/api/send-outreach', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          company_name: client.name,
          company_description: client.relevance_reason || `${client.name} operating in ${client.industry || 'B2B'}`,
          contact_email: contacts.primary_email,
          subject: emailSubject,
          body: emailBody,
        }),
      });

      const data = await res.json();
      if (!res.ok || data.error) throw new Error(data.error || 'Failed to send outreach email');

      setSendSuccess(`Email successfully sent to ${contacts.primary_email}!`);

      // Auto-update client status to 'Contacted' so lead moves on Task Board & DB
      if (client.status !== 'Contacted') {
        setClient(prev => prev ? { ...prev, status: 'Contacted' } : null);
        fetch(`/api/clients/${client.id}`, {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ status: 'Contacted' }),
        }).catch(err => console.warn('[Auto Contacted Status Error]', err));
      }
    } catch (err) {
      setSendError(err instanceof Error ? err.message : 'Failed to send email');
    } finally {
      setSendingEmail(false);
    }
  }, [client, emailSubject, emailBody, contacts.primary_email]);

  // SMTP Real Email Dispatcher & Animated Sent Modal State
  const [sendingSmtp, setSendingSmtp] = useState(false);
  const [smtpSuccessMsg, setSmtpSuccessMsg] = useState<string | null>(null);
  const [showSentModal, setShowSentModal] = useState(false);
  const [sentModalData, setSentModalData] = useState<{ recipient: string; subject: string; label: string } | null>(null);

  const handleSendRealEmail = useCallback(async () => {
    if (!client || !emailSubject || !emailBody) return;
    const cleanDomain = client.website ? client.website.replace(/^https?:\/\//i, '').replace(/\/.*$/, '') : '';
    const recipient = contacts.primary_email || client.email || (cleanDomain ? `contact@${cleanDomain}` : 'contact@company.com');

    setSendingSmtp(true);
    setEmailError(null);
    setSmtpSuccessMsg(null);

    try {
      const token = getAuthToken();
      const res = await fetch('/api/send-email', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({
          client_id: client.id,
          recipient_email: recipient,
          subject: emailSubject,
          body: emailBody,
          email_type: 'outreach',
        }),
      });

      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || data.error || 'Failed to deliver real email via SMTP');

      const entryLabel = data.history_entry?.label || 'Cold Outreach 1';
      setSmtpSuccessMsg(data.message || `Real email delivered to ${recipient}!`);
      setSentModalData({
        recipient,
        subject: emailSubject,
        label: entryLabel
      });
      setShowSentModal(true);

      if (client.status !== 'Contacted') {
        setClient(prev => prev ? { ...prev, status: 'Contacted' } : null);
      }

      fetchEmailHistory();
    } catch (err) {
      setEmailError(err instanceof Error ? err.message : 'SMTP Email delivery failed');
    } finally {
      setSendingSmtp(false);
    }
  }, [client, emailSubject, emailBody, contacts.primary_email, fetchEmailHistory]);

  const handleGenerateEmail = useCallback(async () => {
    if (!client) return;
    setEmailGenerating(true);
    setEmailError(null);
    setEmailCopied(false);

    try {
      const token = getAuthToken();
      const res = await fetch('/api/generate-outreach-email', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({
          company_name: client.name,
          industry: client.industry,
          country: client.country,
          company_summary: client.relevance_reason || `${client.name} is a company operating in ${client.industry}.`,
          matched_service: (pitchType === 'targeted' && (client.search_query || customKeyword)) 
            ? (client.search_query || customKeyword) 
            : (client.matched_service || ourServices || 'our B2B services'),
          match_reason: (pitchType === 'targeted' && (client.search_query || customKeyword))
            ? `implementing and optimizing ${client.search_query || customKeyword} solutions for ${client.name}`
            : (client.match_reason || `optimizing operations for ${client.name}`),
        }),
      });

      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'Failed to generate outreach email');

      const subj = data.subject || `${ourServices || 'B2B Solutions'} for ${client.name}`;
      const bdy = data.body || '';
      setEmailSubject(subj);
      setEmailBody(bdy);
      autoSaveToHistory('outreach', subj, bdy);

      // Step 2 Automation: Auto-update status to 'Contacted' so lead moves on Task Board
      if (client.status !== 'Contacted') {
        setClient(prev => prev ? { ...prev, status: 'Contacted' } : null);
        fetch(`/api/clients/${client.id}`, {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ status: 'Contacted' }),
        }).catch(err => console.warn('[Auto Contacted Status Error]', err));
      }
    } catch (err) {
      setEmailError(err instanceof Error ? err.message : 'Email generation failed');
    } finally {
      setEmailGenerating(false);
    }
  }, [client, ourServices, pitchType, customKeyword, autoSaveToHistory]);

  const handleGenerateFollowup = useCallback(async () => {
    if (!client) return;
    setEmailGenerating(true);
    setEmailError(null);
    setEmailCopied(false);

    try {
      const token = getAuthToken();
      const res = await fetch('/api/generate-outreach-email', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({
          company_name: client.name,
          industry: client.industry,
          country: client.country,
          company_summary: client.relevance_reason || `${client.name} is a company operating in ${client.industry}.`,
          matched_service: (pitchType === 'targeted' && (client.search_query || customKeyword)) 
            ? (client.search_query || customKeyword) 
            : (client.matched_service || ourServices || 'our B2B services'),
          is_followup: true,
        }),
      });

      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'Failed to generate follow-up email');

      const subj = data.subject || `Following up: ${ourServices || 'B2B Solutions'} for ${client.name}`;
      const bdy = data.body || '';
      setEmailSubject(subj);
      setEmailBody(bdy);
      autoSaveToHistory('followup', subj, bdy);
    } catch (err) {
      setEmailError(err instanceof Error ? err.message : 'Follow-up email generation failed');
    } finally {
      setEmailGenerating(false);
    }
  }, [client, ourServices, pitchType, customKeyword, autoSaveToHistory]);

  // Negotiation Assistant State
  const [clientReplyInput, setClientReplyInput] = useState('');
  const [negotiationResult, setNegotiationResult] = useState<{
    objection_type: string;
    detected_intent: string;
    strategy_hint: string;
    subject: string;
    body: string;
  } | null>(null);
  const [analyzingNegotiation, setAnalyzingNegotiation] = useState(false);
  const [negotiationError, setNegotiationError] = useState<string | null>(null);

  const handleAnalyzeNegotiation = useCallback(async () => {
    if (!client || !clientReplyInput.trim()) return;
    setAnalyzingNegotiation(true);
    setNegotiationError(null);

    try {
      const token = getAuthToken();
      const res = await fetch('/api/analyze-negotiation', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({
          company_name: client.name,
          industry: client.industry,
          country: client.country,
          company_summary: client.relevance_reason || `${client.name} is operating in ${client.industry}.`,
          matched_service: client.matched_service || ourServices || 'our B2B services',
          client_reply: clientReplyInput,
        }),
      });

      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'Failed to analyze negotiation reply');

      setNegotiationResult(data);
      const subj = data.subject || `Re: Proposal for ${client.name}`;
      const bdy = data.body || '';
      if (data.subject) setEmailSubject(data.subject);
      if (data.body) setEmailBody(data.body);
      autoSaveToHistory('negotiation', subj, bdy);

      // Auto-update client status to 'In Negotiation' so lead moves on Task Board
      if (client.status !== 'In Negotiation') {
        setClient(prev => prev ? { ...prev, status: 'In Negotiation' } : null);
        fetch(`/api/clients/${client.id}`, {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ status: 'In Negotiation' }),
        }).catch(err => console.warn('[Auto Negotiation Status Error]', err));
      }
    } catch (err) {
      setNegotiationError(err instanceof Error ? err.message : 'Negotiation analysis failed');
    } finally {
      setAnalyzingNegotiation(false);
    }
  }, [client, clientReplyInput, ourServices, autoSaveToHistory]);

  // Load client data
  useEffect(() => {
    async function load() {
      try {
        const token = getAuthToken();
        const res   = await fetch(`/api/clients/${id}`, {
          headers: token ? { 'Authorization': `Bearer ${token}` } : {},
        });
        const data  = await res.json();
        if (!res.ok) throw new Error(data.error || 'Client not found');
        setClient(data.client);
        if (data.client?.search_query) {
          setPitchType('targeted');
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load');
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [id]);

  // ── Stage 2 enrichment: load from Supabase or poll until ready ────────────
  useEffect(() => {
    if (activeTab !== 'Contact Info' || !client) return;
    if (stage2State === 'done' || stage2State === 'polling') return;

    function applyStage2Data(raw: Client) {
      // Parse Stage 2 JSON from contact_source_context
      let stage2: Partial<ContactData> | null = null;
      if (raw.contact_source_context) {
        try {
          const parsed = JSON.parse(raw.contact_source_context);
          if (parsed && Array.isArray(parsed.all_emails)) stage2 = parsed;
        } catch {}
      }

      if (stage2) {
        // Stage 2 complete — use its data, fall back to base fields
        const primaryEmail = (stage2.all_emails && stage2.all_emails[0]) || raw.email || null;
        const phones = Array.isArray(stage2.phones) && stage2.phones.length > 0
          ? stage2.phones
          : raw.phones ? raw.phones.split(',').map(s => s.trim()).filter(Boolean) : [];
        const linkedinCompany = stage2.linkedin_company || raw.linkedin_company || null;
        const linkedinPeople = Array.isArray(stage2.linkedin_people) ? stage2.linkedin_people : [];
        const contactPageUrl = stage2.contact_page_url || raw.contact_source_url ||
          (raw.website ? `${raw.website.replace(/\/+$/, '')}/contact-us` : null);

        const outreachSuggestion = primaryEmail
          ? `Primary email (${primaryEmail}) verified. Suggested: Cold Email outreach + LinkedIn connect.`
          : linkedinCompany
          ? `No public email found. Suggested: LinkedIn Company Outreach & InMail.`
          : `Contact via website form at ${contactPageUrl || raw.website}.`;

        setContacts({
          primary_email: primaryEmail,
          all_emails: stage2.all_emails || (raw.email ? [raw.email] : []),
          email_meta: stage2.email_meta || [],
          phones,
          linkedin_company: linkedinCompany,
          linkedin_people: linkedinPeople,
          contact_page_url: contactPageUrl,
          source_label: stage2.source_label || 'Stage 2 Deep Crawl',
          source_context: '',
          outreach_suggestion: outreachSuggestion,
          found: Boolean(primaryEmail || phones.length > 0 || linkedinCompany || linkedinPeople.length > 0),
          loading: false,
        });
        setStage2State('done');
        if (pollRef.current) clearInterval(pollRef.current);
        return true;
      }

      // Stage 2 not yet done — seed with Stage 1 data from base columns
      const primaryEmail = raw.email || null;
      const phones = raw.phones ? raw.phones.split(',').map(s => s.trim()).filter(Boolean)
        : (raw.phone ? [raw.phone] : []);
      const linkedinCompany = raw.linkedin_company || null;
      const contactPageUrl = raw.contact_source_url ||
        (raw.website ? `${raw.website.replace(/\/+$/, '')}/contact-us` : null);

      setContacts({
        primary_email: primaryEmail,
        all_emails: primaryEmail ? [primaryEmail] : [],
        email_meta: [],
        phones,
        linkedin_company: linkedinCompany,
        linkedin_people: [],
        contact_page_url: contactPageUrl,
        source_label: raw.contact_source_label || 'Stage 1 (fast crawl)',
        source_context: '',
        found: Boolean(primaryEmail || phones.length > 0 || linkedinCompany),
        loading: false,
      });
      return false; // Stage 2 not done yet
    }

    const alreadyDone = applyStage2Data(client as Client);
    if (alreadyDone) return;

    // Stage 2 not in Supabase yet — start polling every 3s up to 60s
    setStage2State('polling');
    pollCountRef.current = 0;
    pollRef.current = setInterval(async () => {
      pollCountRef.current += 1;
      if (pollCountRef.current > 20) { // 20 × 3s = 60s
        clearInterval(pollRef.current!);
        setStage2State('timeout');
        return;
      }
      try {
        const res = await fetch(`/api/clients/${id}`);
        if (!res.ok) return;
        const data = await res.json();
        if (data.client) {
          const done = applyStage2Data(data.client as Client);
          if (done) setStage2State('done');
        }
      } catch {}
    }, 3000);

    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, [activeTab, client, id]);

  const toggleTask = (i: number) => {
    setTasks(prev => prev.map((t, idx) => idx === i ? { ...t, done: !t.done } : t));
  };

  // ── Loading ──────────────────────────────────────────────────────────────
  if (loading) {
    return (
      <div className="p-6 max-w-5xl mx-auto space-y-4">
        <div className="h-5 w-40 rounded shimmer" />
        <div className="bg-white rounded-2xl p-5 border border-outline-variant soft-shadow">
          <div className="flex gap-4 items-center">
            <div className="w-16 h-16 rounded-2xl shimmer flex-shrink-0" />
            <div className="space-y-2 flex-1">
              <div className="h-7 w-48 rounded shimmer" />
              <div className="h-4 w-72 rounded shimmer" />
            </div>
          </div>
        </div>
        <div className="h-64 rounded-2xl shimmer" />
      </div>
    );
  }

  if (error || !client) {
    return (
      <div className="p-6 flex flex-col items-center justify-center min-h-[60vh] text-center">
        <span className="material-symbols-outlined text-5xl mb-3 text-red-400">error</span>
        <p className="text-[18px] font-semibold text-red-600">{error || 'Client not found'}</p>
        <Link href="/clients" className="mt-4 text-primary hover:underline font-medium">← Back to Clients</Link>
      </div>
    );
  }

  const initials   = client.name.split(/\s+/).slice(0, 2).map(w => w[0]?.toUpperCase() ?? '').join('');
  const logoColor  = LOGO_COLORS[client.name.charCodeAt(0) % LOGO_COLORS.length];
  const score      = client.trust_score ?? 0;
  const trustLabel = getTrustLabel(score);
  const statusStyle = STATUS_STYLES[client.status] ?? STATUS_STYLES.Pending;
  const domain     = client.website ? getDomain(client.website) : '';
  const doneCount  = tasks.filter(t => t.done).length;

  return (
    <div className="p-4 md:p-6 pb-10">
      <div className="max-w-5xl mx-auto space-y-5">

        {/* Breadcrumb */}
        <nav className="flex items-center gap-1.5 text-[13px] text-secondary">
          <Link href="/clients" className="hover:text-primary transition-colors">Clients</Link>
          <span className="material-symbols-outlined text-[14px]">chevron_right</span>
          <span className="text-on-surface font-medium">{client.name}</span>
        </nav>

        {/* Header Card */}
        <motion.div
          className="bg-white rounded-2xl p-5 border border-outline-variant soft-shadow"
          initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}
        >
          <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
            {/* Logo + Name */}
            <div className="flex items-center gap-4">
              <div className={`w-14 h-14 rounded-2xl flex items-center justify-center text-white font-bold text-xl flex-shrink-0 overflow-hidden ${client.logo_url ? 'bg-white border border-outline-variant' : logoColor}`}>
                {client.logo_url ? (
                  <img src={client.logo_url} alt={initials} className="w-full h-full object-contain p-1"
                    onError={e => { (e.target as HTMLImageElement).style.display = 'none'; }} />
                ) : initials}
              </div>
              <div>
                <div className="flex items-center gap-2 flex-wrap mb-1">
                  <h1 className="text-[24px] font-bold text-on-surface">{client.name}</h1>
                  <span className={`px-2 py-0.5 rounded-lg text-[11px] font-semibold border ${statusStyle}`}>
                    {client.status || 'Pending'}
                  </span>
                </div>
                <div className="flex flex-wrap items-center gap-3 text-secondary text-[13px]">
                  {domain && (
                    <a href={client.website?.startsWith('http') ? client.website : `https://${client.website}`}
                      target="_blank" rel="noreferrer"
                      className="flex items-center gap-1 hover:text-primary transition-colors">
                      <span className="material-symbols-outlined text-[14px]">language</span>{domain}
                    </a>
                  )}
                  {client.industry && <span className="flex items-center gap-1"><span className="material-symbols-outlined text-[14px]">domain</span>{client.industry}</span>}
                  {client.country  && <span className="flex items-center gap-1"><span className="material-symbols-outlined text-[14px]">location_on</span>{client.country}</span>}
                </div>
              </div>
            </div>

            {/* Trust Score */}
            <div className="flex items-center gap-3 bg-gray-50 px-4 py-3 rounded-xl border border-gray-200">
              <div className="text-right">
                <p className="text-[10px] font-semibold uppercase tracking-wider text-gray-400">AI Score</p>
                <p className="text-[14px] font-bold text-gray-700">{trustLabel}</p>
              </div>
              <div className="relative w-12 h-12">
                <svg className="w-full h-full -rotate-90" viewBox="0 0 100 100">
                  <circle cx="50" cy="50" r="42" fill="none" stroke="#e5e7eb" strokeWidth="10" />
                  <motion.circle cx="50" cy="50" r="42" fill="none" stroke="#2563eb" strokeWidth="10" strokeLinecap="round"
                    strokeDasharray="264"
                    initial={{ strokeDashoffset: 264 }}
                    animate={{ strokeDashoffset: 264 - (264 * score / 100) }}
                    transition={{ delay: 0.3, duration: 1, ease: 'easeOut' }}
                  />
                </svg>
                <div className="absolute inset-0 flex items-center justify-center">
                  <span className="text-[13px] font-bold text-blue-600">{score}</span>
                </div>
              </div>
            </div>
          </div>
        </motion.div>

        {/* Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">

          {/* Left: Tabs */}
          <div className="lg:col-span-7 flex flex-col gap-4">

            {/* Tab Bar */}
            <div className="bg-white border border-outline-variant rounded-2xl px-2 flex gap-1">
              {tabs.map(tab => (
                <button key={tab} onClick={() => setActiveTab(tab)}
                  className={`relative py-3.5 px-3 text-[13px] font-medium transition-colors whitespace-nowrap ${
                    activeTab === tab ? 'text-primary' : 'text-secondary hover:text-primary'
                  }`}>
                  {tab}
                  {activeTab === tab && (
                    <motion.div layoutId="underline"
                      className="absolute bottom-0 left-0 right-0 h-0.5 bg-primary rounded-full"
                      transition={{ type: 'spring', stiffness: 500, damping: 40 }} />
                  )}
                </button>
              ))}
            </div>

            <AnimatePresence mode="wait">

              {/* ── Overview ──────────────────────────────────────────── */}
              {activeTab === 'Overview' && (
                <motion.div key="ov" className="flex flex-col gap-4"
                  initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}>

                  {/* AI Qualification & Benefit Overview */}
                  <div className="bg-white rounded-2xl p-5 border border-outline-variant soft-shadow space-y-4">
                    <div className="flex items-center justify-between border-b border-gray-100 pb-3">
                      <h3 className="text-[15px] font-bold text-on-surface flex items-center gap-2">
                        <span className="material-symbols-outlined text-primary text-[19px]">auto_awesome</span>
                        Company Overview & Value Fit
                      </h3>
                      <span className="text-[11px] font-semibold text-blue-700 bg-blue-50 px-2.5 py-0.5 rounded-full border border-blue-100">
                        {ourCompanyName} AI Analysis
                      </span>
                    </div>

                    {/* Company Overview / Qualification Summary */}
                    <div className="space-y-1">
                      <p className="text-[11px] font-semibold uppercase tracking-wider text-gray-400">Company Overview</p>
                      <p className="text-[13.5px] text-gray-700 leading-relaxed font-normal">
                        {client.relevance_reason || `${client.name} is a company operating in the ${client.industry || 'commercial'} sector in ${client.country || 'Global'}.`}
                      </p>
                    </div>

                    {/* Highlighted Short Benefit Banner */}
                    <div className="bg-gradient-to-r from-blue-50/80 to-indigo-50/80 rounded-xl p-3.5 border border-blue-100 flex items-start gap-2.5">
                      <span className="material-symbols-outlined text-blue-600 text-[18px] mt-0.5 shrink-0">trending_up</span>
                      <div className="text-[13px] leading-snug">
                        <span className="font-bold text-blue-900">Key Benefit: </span>
                        <span className="text-blue-950 font-medium">
                          {(client as any).match_reason 
                            ? `Can leverage ${(client as any).matched_service || ourServices} for ${(client as any).match_reason}.`
                            : `Can leverage ${ourCompanyName} solutions to automate site servicing, optimize workflows, and increase operational efficiency.`
                          }
                        </span>
                      </div>
                    </div>
                  </div>

                  {/* Basic Info */}
                  <div className="bg-white rounded-2xl border border-outline-variant soft-shadow">
                    <div className="px-5 py-3.5 border-b border-gray-100 flex items-center gap-2">
                      <span className="material-symbols-outlined text-primary text-[17px]">info</span>
                      <h3 className="text-[14px] font-semibold text-on-surface">Company Details</h3>
                    </div>
                    <div className="px-5 py-1">
                      <ContactItem icon="business"       label="Name"     value={client.name} />
                      <ContactItem icon="domain"         label="Industry" value={client.industry || '—'} />
                      <ContactItem icon="location_on"    label="Country"  value={client.country  || '—'} />
                      {domain && <ContactItem icon="language" label="Website" value={domain}
                        href={client.website?.startsWith('http') ? client.website : `https://${client.website}`}
                        iconColor="text-blue-500" />}
                      <ContactItem icon="flag"           label="Status"   value={client.status || 'Pending'} />
                      <ContactItem icon="calendar_today" label="Added"
                        value={new Date(client.created_at).toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' })} />
                    </div>
                  </div>
                </motion.div>
              )}

              {/* ── Contact Info ───────────────────────────────────────── */}
              {activeTab === 'Contact Info' && (
                <motion.div key="ci" className="bg-white rounded-2xl border border-outline-variant soft-shadow flex flex-col space-y-4 p-5"
                  initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}>

                  <div className="flex items-center justify-between border-b border-gray-100 pb-3">
                    <div className="flex items-center gap-2">
                      <span className="material-symbols-outlined text-primary text-[20px]">contacts</span>
                      <h3 className="text-[16px] font-bold text-on-surface">Contact Information</h3>
                    </div>
                    {/* Stage 2 loading / status banner */}
                    {stage2State === 'polling' && (
                      <div className="flex items-center gap-1.5 text-[12px] text-blue-600 font-medium bg-blue-50 px-2.5 py-1 rounded-full border border-blue-200">
                        <svg className="animate-spin w-3.5 h-3.5" fill="none" viewBox="0 0 24 24">
                          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
                        </svg>
                        Deep crawl in progress...
                      </div>
                    )}
                    {stage2State === 'done' && (
                      <div className="flex items-center gap-1 text-[11px] text-emerald-600 font-semibold bg-emerald-50 px-2.5 py-1 rounded-full border border-emerald-200">
                        <span className="material-symbols-outlined text-[14px]">verified</span>
                        Stage 2 enriched
                      </div>
                    )}
                    {stage2State === 'timeout' && (
                      <div className="text-[11px] text-amber-700 font-medium bg-amber-50 px-2.5 py-1 rounded-full border border-amber-200">
                        Still gathering — check back shortly
                      </div>
                    )}
                  </div>

                  {/* 1. Primary Email (Highlighted) */}
                  {contacts.primary_email ? (
                    <div className="bg-gradient-to-r from-blue-50 to-indigo-50 border border-blue-200 rounded-xl p-4 flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-xl bg-blue-600 text-white flex items-center justify-center shadow-sm">
                          <span className="material-symbols-outlined text-[20px]">mail</span>
                        </div>
                        <div>
                          <div className="text-[11px] font-semibold uppercase tracking-wider text-blue-700">Primary Contact Email</div>
                          <a href={`mailto:${contacts.primary_email}`} className="text-[16px] font-bold text-blue-950 hover:underline">
                            {contacts.primary_email}
                          </a>
                        </div>
                      </div>
                      <CopyBtn value={contacts.primary_email} />
                    </div>
                  ) : !contacts.loading && (
                    <div className="bg-gray-50 border border-gray-200 rounded-xl p-3.5 flex items-center gap-2.5 text-gray-500 text-[13px]">
                      <span className="material-symbols-outlined text-gray-400">mail_lock</span>
                      <span>No primary email identified yet</span>
                    </div>
                  )}

                  {/* 2. All Emails List with Source Reference */}
                  {contacts.all_emails.length > 0 && (() => {
                    const uniqueEmails = Array.from(
                      new Map(contacts.all_emails.map(e => [e.toLowerCase(), e])).values()
                    );

                    return (
                      <div className="space-y-2">
                        <h4 className="text-[13px] font-semibold text-gray-700 flex items-center gap-1.5">
                          <span className="material-symbols-outlined text-[16px] text-primary">mark_email_read</span>
                          All Extracted Emails & Source References
                        </h4>
                        <div className="bg-surface-container-low rounded-xl p-3 border border-outline-variant/40 divide-y divide-gray-100">
                          {uniqueEmails.map((em, idx) => {
                            const meta = contacts.email_meta.find(m => m.email?.toLowerCase() === em.toLowerCase());

                            let sourcesList: Array<{ name: string; url: string }> = [];

                            if (meta && Array.isArray((meta as any).sources) && (meta as any).sources.length > 0) {
                              sourcesList = (meta as any).sources.map((s: any) => ({
                                name: s.page || getCleanPageName(s.url),
                                url: s.url
                              }));
                            } else if (meta?.source_page || meta?.source_url) {
                              sourcesList = [{
                                name: getCleanPageName(meta.source_url || meta.source_page),
                                url: meta.source_url || ''
                              }];
                            } else {
                              sourcesList = [{
                                name: contacts.source_label ? getCleanPageName(contacts.source_label) : 'Contact Page',
                                url: contacts.contact_page_url || ''
                              }];
                            }

                            // Filter out any technical 'SOURCE_URL:' strings if present
                            sourcesList = sourcesList.map(s => ({
                              ...s,
                              name: s.name.replace(/^SOURCE_URL:\s*/i, '').trim()
                            })).filter(s => s.name);

                            // Deduplicate sources by page name
                            const uniqueSources = Array.from(
                              new Map(sourcesList.map(s => [s.name, s])).values()
                            );

                            return (
                              <div key={idx} className="py-2.5 first:pt-1 last:pb-1 flex flex-col gap-1.5">
                                <div className="flex items-center justify-between gap-2">
                                  <div className="flex items-center gap-2 min-w-0">
                                    <span className="material-symbols-outlined text-[16px] text-blue-500 flex-shrink-0">alternate_email</span>
                                    <a href={`mailto:${em}`} className="font-semibold text-blue-700 hover:underline text-[14px] truncate">
                                      {em}
                                    </a>
                                  </div>
                                  <CopyBtn value={em} />
                                </div>
                                <div className="flex items-center gap-2 text-[12px] text-gray-500 pl-6">
                                  <span className="font-medium text-gray-400">Found on:</span>
                                  <div className="flex flex-wrap gap-1.5 items-center">
                                    {uniqueSources.map((src, sIdx) => (
                                      <a
                                        key={sIdx}
                                        href={src.url && src.url.startsWith('http') ? src.url : (contacts.contact_page_url || '#')}
                                        target="_blank"
                                        rel="noreferrer"
                                        title={src.url ? `Source URL: ${src.url}` : 'Page source'}
                                        className="inline-flex items-center gap-1 bg-gray-100 hover:bg-blue-50 text-gray-700 hover:text-blue-700 px-2 py-0.5 rounded-md font-medium text-[11px] transition-colors border border-gray-200/60"
                                      >
                                        {src.name}
                                        <span className="material-symbols-outlined text-[10px] opacity-60">open_in_new</span>
                                      </a>
                                    ))}
                                  </div>
                                </div>
                              </div>
                            );
                          })}
                        </div>
                      </div>
                    );
                  })()}

                  {/* 3. All Phone Numbers */}
                  {contacts.phones.length > 0 && (
                    <div className="space-y-2">
                      <h4 className="text-[13px] font-semibold text-gray-700 flex items-center gap-1.5">
                        <span className="material-symbols-outlined text-[16px] text-emerald-600">call</span>
                        All Phone Numbers
                      </h4>
                      <div className="bg-surface-container-low rounded-xl p-3 border border-outline-variant/40 flex flex-wrap gap-3">
                        {contacts.phones.map((phone, idx) => (
                          <div key={idx} className="flex items-center gap-2 bg-white px-3 py-1.5 rounded-lg border border-gray-200">
                            <span className="material-symbols-outlined text-[16px] text-emerald-600">phone_in_talk</span>
                            <a href={`tel:${phone}`} className="font-semibold text-gray-800 hover:text-emerald-700 text-[13px]">
                              {phone}
                            </a>
                            <CopyBtn value={phone} />
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* 4. LinkedIn Company URL & 5. LinkedIn People profiles */}
                  {(contacts.linkedin_company || contacts.linkedin_people.length > 0) && (
                    <div className="space-y-2">
                      <h4 className="text-[13px] font-semibold text-gray-700 flex items-center gap-1.5">
                        <span className="material-symbols-outlined text-[16px] text-[#0077b5]">groups</span>
                        LinkedIn Presence & Team Profiles
                      </h4>
                      <div className="bg-blue-50/50 rounded-xl p-3 border border-blue-100 space-y-2">
                        {contacts.linkedin_company && (
                          <div className="flex items-center justify-between text-[13px]">
                            <div className="flex items-center gap-2">
                              <span className="material-symbols-outlined text-[16px] text-[#0077b5]">domain</span>
                              <span className="font-medium text-gray-600">Company Page:</span>
                              <a href={contacts.linkedin_company} target="_blank" rel="noreferrer" className="font-semibold text-blue-700 hover:underline">
                                {contacts.linkedin_company.replace(/^https?:\/\/(www\.)?/, '')}
                              </a>
                            </div>
                            <CopyBtn value={contacts.linkedin_company} />
                          </div>
                        )}
                        {contacts.linkedin_people.map((pUrl, idx) => (
                          <div key={idx} className="flex items-center justify-between text-[13px] pt-1 border-t border-blue-100/60">
                            <div className="flex items-center gap-2">
                              <span className="material-symbols-outlined text-[16px] text-purple-600">person</span>
                              <span className="font-medium text-gray-600">People Profile #{idx + 1}:</span>
                              <a href={pUrl} target="_blank" rel="noreferrer" className="font-semibold text-purple-700 hover:underline">
                                {pUrl.replace(/^https?:\/\/(www\.)?/, '')}
                              </a>
                            </div>
                            <CopyBtn value={pUrl} />
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* 6. Contact Page Direct Link */}
                  {contacts.contact_page_url && (
                    <div className="flex items-center justify-between bg-surface-container-low p-3 rounded-xl border border-outline-variant/40 text-[13px]">
                      <div className="flex items-center gap-2 text-gray-600">
                        <span className="material-symbols-outlined text-[18px] text-primary">link</span>
                        <span>Contact Page Direct Link:</span>
                        <a href={contacts.contact_page_url} target="_blank" rel="noreferrer" className="font-bold text-primary hover:underline">
                          {contacts.contact_page_url} ↗
                        </a>
                      </div>
                      <CopyBtn value={contacts.contact_page_url} />
                    </div>
                  )}

                  {/* 7. Best Outreach Suggestion */}
                  {contacts.outreach_suggestion && (
                    <div className="bg-amber-50/70 border border-amber-200 rounded-xl p-4 space-y-1">
                      <div className="flex items-center gap-2 text-amber-900 font-bold text-[13px]">
                        <span className="material-symbols-outlined text-[18px] text-amber-600">auto_awesome</span>
                        Recommended Outreach Strategy
                      </div>
                      <p className="text-[13px] text-amber-950 leading-relaxed font-medium">
                        {contacts.outreach_suggestion}
                      </p>
                    </div>
                  )}

                  {/* Not found fallback */}
                  {!contacts.loading && !contacts.found && (
                    <div className="p-6 text-center text-[13px] text-gray-400">
                      <span className="material-symbols-outlined text-4xl block mb-2 text-gray-300">search_off</span>
                      Could not find contact info for <strong>{client.name}</strong> automatically.
                      <br />Try searching manually on{' '}
                      <a href={`https://www.linkedin.com/company/${client.name.toLowerCase().replace(/\s+/g, '-')}`}
                        target="_blank" rel="noreferrer" className="text-blue-500 hover:underline">LinkedIn</a>.
                    </div>
                  )}
                </motion.div>
              )}

              {/* ── AI Outreach Email Tab ──────────────────────────────── */}
              {activeTab === 'Outreach Email' && (
                <motion.div key="oe" className="bg-white rounded-2xl p-6 border border-outline-variant soft-shadow space-y-5"
                  initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}>
                  
                  <div className="flex items-center justify-between border-b border-gray-100 pb-4">
                    <div className="flex items-center gap-2.5">
                      <div className="w-9 h-9 rounded-xl bg-blue-50 text-blue-600 flex items-center justify-center">
                        <span className="material-symbols-outlined text-[20px]">auto_awesome</span>
                      </div>
                      <div>
                        <h3 className="text-[16px] font-bold text-on-surface">AI Personalized Outreach Email</h3>
                        <p className="text-[12px] text-gray-500">Tailored cold outreach generated with Groq AI for {client.name}</p>
                      </div>
                    </div>
                    {emailBody && (
                      <button
                        onClick={handleGenerateEmail}
                        disabled={emailGenerating}
                        className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-gray-100 text-gray-700 hover:bg-gray-200 text-[12px] font-semibold transition-colors disabled:opacity-50"
                      >
                        <span className={`material-symbols-outlined text-[15px] ${emailGenerating ? 'animate-spin' : ''}`}>
                          {emailGenerating ? 'progress_activity' : 'refresh'}
                        </span>
                        {emailGenerating ? 'Generating...' : 'Regenerate'}
                      </button>
                    )}
                  </div>
                  {/* Campaign pitch target selector */}
                  <div className="bg-blue-50/70 border border-blue-100 rounded-xl p-4 flex flex-col gap-3.5 text-[13px]">
                    <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
                      <div className="space-y-0.5">
                        <span className="font-bold text-blue-900 block">Outreach Campaign Goal</span>
                        <p className="text-blue-950/80 leading-snug">
                          {client?.search_query ? (
                            <>
                              This lead was discovered via search keyword <strong className="text-blue-800">"{client.search_query}"</strong>.
                            </>
                          ) : (
                            <>
                              No discovery keyword found. You can set a custom target niche/service below.
                            </>
                          )}
                        </p>
                      </div>
                      <div className="flex gap-2 shrink-0">
                        <button
                          onClick={() => setPitchType('targeted')}
                          className={`px-3 py-1.5 rounded-lg text-[12px] font-bold transition-all border ${
                            pitchType === 'targeted'
                              ? 'bg-blue-600 text-white border-blue-600 shadow-sm'
                              : 'bg-white text-gray-700 border-gray-200 hover:bg-gray-50'
                          }`}
                        >
                          Targeted Niche Pitch
                        </button>
                        <button
                          onClick={() => setPitchType('general')}
                          className={`px-3 py-1.5 rounded-lg text-[12px] font-bold transition-all border ${
                            pitchType === 'general'
                              ? 'bg-blue-600 text-white border-blue-600 shadow-sm'
                              : 'bg-white text-gray-700 border-gray-200 hover:bg-gray-50'
                          }`}
                        >
                          General Company Intro
                        </button>
                      </div>
                    </div>

                    {/* Custom keyword text input field (rendered if no client search_query or when targeted pitch is active) */}
                    {pitchType === 'targeted' && (
                      <div className="border-t border-blue-100/60 pt-3 flex flex-col sm:flex-row items-start sm:items-center gap-2">
                        <span className="font-semibold text-blue-900 whitespace-nowrap">Target Service/Niche:</span>
                        {client?.search_query ? (
                          <div className="flex items-center gap-2">
                            <span className="px-2.5 py-1 bg-blue-100 text-blue-800 rounded-lg font-bold text-[12px] border border-blue-200">
                              {client.search_query}
                            </span>
                            <button
                              onClick={() => {
                                setCustomKeyword(client.search_query || '');
                                setClient(prev => prev ? { ...prev, search_query: null } : null);
                              }}
                              className="text-[11px] text-blue-600 hover:underline"
                            >
                              Edit
                            </button>
                          </div>
                        ) : (
                          <input
                            type="text"
                            value={customKeyword}
                            onChange={(e) => setCustomKeyword(e.target.value)}
                            placeholder="e.g. AI chatbot, mobile app development, CRM integration..."
                            className="flex-1 w-full px-3 py-1.5 rounded-lg border border-blue-200 focus:outline-none focus:ring-1 focus:ring-blue-500 bg-white text-gray-800 text-[12px] shadow-inner"
                          />
                        )}
                      </div>
                    )}
                  </div>

                  {emailGenerating ? (
                    <div className="py-12 text-center space-y-3">
                      <div className="inline-flex items-center justify-center w-12 h-12 rounded-2xl bg-blue-50 text-blue-600 animate-pulse">
                        <span className="material-symbols-outlined text-2xl">auto_awesome</span>
                      </div>
                      <p className="text-[14px] font-semibold text-gray-700">Writing personalized cold email for {client.name}...</p>
                      <p className="text-[12px] text-gray-400">Analyzing company details & {ourCompanyName} service alignment</p>
                    </div>
                  ) : emailError ? (
                    <div className="p-4 rounded-xl bg-red-50 border border-red-200 text-[13px] text-red-700 flex items-center justify-between">
                      <span>{emailError}</span>
                      <button onClick={handleGenerateEmail} className="px-3 py-1 bg-red-600 text-white rounded-lg text-[12px] font-semibold">Try Again</button>
                    </div>
                  ) : !emailBody ? (
                    <div className="py-10 text-center space-y-4 bg-gray-50/60 rounded-2xl border border-dashed border-gray-200 p-6">
                      <div className="w-12 h-12 rounded-2xl bg-blue-100 text-blue-600 mx-auto flex items-center justify-center">
                        <span className="material-symbols-outlined text-2xl">mail_lock</span>
                      </div>
                      <div>
                        <h4 className="text-[15px] font-bold text-gray-800">No Email Generated Yet</h4>
                        <p className="text-[13px] text-gray-500 max-w-md mx-auto mt-1">
                          Generate a personalized cold outreach email referencing {client.name}'s specific business and {ourCompanyName} solutions.
                        </p>
                      </div>
                      <button
                        onClick={handleGenerateEmail}
                        className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-blue-600 hover:bg-blue-700 text-white font-semibold text-[13px] transition-all shadow-sm"
                      >
                        <span className="material-symbols-outlined text-[18px]">auto_awesome</span>
                        Generate Outreach Email Now
                      </button>
                    </div>
                  ) : (
                    <div className="space-y-5">
                      {/* 🤝 AI Negotiation Assistant & Counter-Offer Generator Panel */}
                      <div className="bg-purple-50/70 border border-purple-200/80 rounded-2xl p-4.5 space-y-3 shadow-2xs">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-2 text-purple-900 font-bold text-[14px]">
                            <span className="material-symbols-outlined text-[20px] text-purple-600">handshake</span>
                            AI Negotiation Assistant & Counter-Offer Strategy
                          </div>
                          <span className="text-[10px] font-extrabold uppercase tracking-wider bg-purple-100 text-purple-800 px-2.5 py-0.5 rounded-full border border-purple-200">
                            Interactive Copilot
                          </span>
                        </div>

                        <p className="text-[12px] text-purple-950/80 leading-relaxed font-medium">
                          Paste any objection or reply received from {client.name} (e.g. price concern, technical query, implementation timeline) to analyze intent and draft a tailored counter-offer.
                        </p>

                        <div className="space-y-2">
                          <textarea
                            value={clientReplyInput}
                            onChange={(e) => setClientReplyInput(e.target.value)}
                            placeholder={`Paste client's email reply or objection here... (e.g. 'Your ${client?.matched_service || 'B2B solutions'} pricing is too high for our current R&D budget...')`}
                            rows={3}
                            className="w-full p-3 bg-white border border-purple-200 rounded-xl text-[13px] text-gray-800 placeholder-gray-400 focus:outline-none focus:border-purple-500 transition-all resize-y shadow-2xs"
                          />

                          <div className="flex items-center justify-between">
                            <button
                              onClick={handleAnalyzeNegotiation}
                              disabled={analyzingNegotiation || !clientReplyInput.trim()}
                              className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-purple-600 hover:bg-purple-700 text-white font-semibold text-[12.5px] transition-all shadow-sm disabled:opacity-50"
                            >
                              <span className={`material-symbols-outlined text-[16px] ${analyzingNegotiation ? 'animate-spin' : ''}`}>
                                {analyzingNegotiation ? 'progress_activity' : 'psychology'}
                              </span>
                              {analyzingNegotiation ? 'Analyzing Strategy...' : 'Analyze Reply & Draft Counter-Offer'}
                            </button>

                            {negotiationError && (
                              <span className="text-[12px] font-semibold text-red-600">{negotiationError}</span>
                            )}
                          </div>
                        </div>

                        {/* Display Analysis Results */}
                        {negotiationResult && (
                          <div className="mt-3 bg-white rounded-xl p-3.5 border border-purple-200 space-y-2.5 shadow-2xs animate-fadeIn">
                            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-gray-100 pb-2">
                              <div className="flex items-center gap-2">
                                <span className="text-[10px] font-bold uppercase tracking-wider bg-purple-100 text-purple-800 px-2 py-0.5 rounded-md border border-purple-200">
                                  Objection: {negotiationResult.objection_type}
                                </span>
                                <span className="text-[12px] text-gray-600 font-medium truncate max-w-md">
                                  Intent: {negotiationResult.detected_intent}
                                </span>
                              </div>
                            </div>

                            <div className="bg-amber-50/70 border border-amber-200 rounded-lg p-2.5 flex items-start gap-2">
                              <span className="material-symbols-outlined text-[18px] text-amber-600 shrink-0 mt-0.5">lightbulb</span>
                              <div>
                                <span className="text-[11px] font-bold uppercase tracking-wider text-amber-900 block">{ourCompanyName} Sales Strategy Advice:</span>
                                <p className="text-[12.5px] text-amber-950 font-medium leading-relaxed">
                                  {negotiationResult.strategy_hint}
                                </p>
                              </div>
                            </div>

                            <p className="text-[11px] text-emerald-700 font-semibold flex items-center gap-1">
                              <span className="material-symbols-outlined text-[14px]">check_circle</span>
                              Counter-offer email drafted and populated in editor below! Status updated to 'In Negotiation'.
                            </p>
                          </div>
                        )}
                      </div>
                      {/* Subject Line */}
                      <div className="space-y-1.5">
                        <label className="text-[11px] font-semibold uppercase tracking-wider text-gray-500 flex items-center justify-between">
                          <span>Subject Line</span>
                          <span className="text-[10px] text-gray-400 font-normal">{emailSubject.length} chars</span>
                        </label>
                        <input
                          type="text"
                          value={emailSubject}
                          onChange={(e) => setEmailSubject(e.target.value)}
                          className="w-full px-3.5 py-2 bg-gray-50 border border-gray-200 rounded-xl text-[14px] font-semibold text-gray-800 focus:bg-white focus:border-blue-500 focus:outline-none transition-all"
                        />
                      </div>

                      {/* Email Body */}
                      <div className="space-y-1.5">
                        <label className="text-[11px] font-semibold uppercase tracking-wider text-gray-500 flex items-center justify-between">
                          <span>Email Body</span>
                          <span className="text-[10px] text-gray-400 font-normal">{emailBody.split(/\s+/).filter(Boolean).length} words</span>
                        </label>
                        <textarea
                          value={emailBody}
                          onChange={(e) => setEmailBody(e.target.value)}
                          rows={10}
                          className="w-full p-4 bg-gray-50 border border-gray-200 rounded-xl text-[14px] leading-relaxed text-gray-800 font-sans focus:bg-white focus:border-blue-500 focus:outline-none transition-all resize-y"
                        />
                      </div>

                      {/* Success & Error Banners for Email Sending */}
                      {sendSuccess && (
                        <div className="p-3.5 rounded-xl bg-emerald-50 border border-emerald-200 text-[13px] text-emerald-800 flex items-center justify-between font-medium animate-fadeIn">
                          <div className="flex items-center gap-2">
                            <span className="material-symbols-outlined text-[18px] text-emerald-600">check_circle</span>
                            <span>{sendSuccess} Client status updated to <strong>Contacted</strong>.</span>
                          </div>
                          <button onClick={() => setSendSuccess(null)} className="text-emerald-700 hover:text-emerald-900 font-bold text-[14px]">✕</button>
                        </div>
                      )}

                      {sendError && (
                        <div className="p-3.5 rounded-xl bg-red-50 border border-red-200 text-[13px] text-red-700 flex items-center justify-between font-medium">
                          <div className="flex items-center gap-2">
                            <span className="material-symbols-outlined text-[18px] text-red-600">error</span>
                            <span>{sendError}</span>
                          </div>
                          <button onClick={() => setSendError(null)} className="text-red-700 hover:text-red-900 font-bold text-[14px]">✕</button>
                        </div>
                      )}

                      {/* Action Buttons */}
                      <div className="flex flex-wrap items-center justify-between gap-3 pt-2 border-t border-gray-100">
                        <div className="flex items-center gap-2 flex-wrap">
                          {/* Primary Direct Send Email Button */}
                          <button
                            onClick={handleSendRealEmail}
                            disabled={sendingSmtp || emailGenerating || !emailBody.trim()}
                            className="flex items-center gap-1.5 px-4.5 py-2.5 rounded-xl bg-blue-600 hover:bg-blue-700 text-white font-bold text-[13.5px] shadow-md shadow-blue-600/25 transition-all disabled:opacity-50 cursor-pointer"
                          >
                            <span className={`material-symbols-outlined text-[19px] ${sendingSmtp ? 'animate-spin' : ''}`}>
                              {sendingSmtp ? 'sync' : 'send'}
                            </span>
                            {sendingSmtp ? 'Sending via Gmail...' : 'Send Real Email (SMTP)'}
                          </button>

                          <button
                            onClick={() => {
                              const fullText = `Subject: ${emailSubject}\n\n${emailBody}`;
                              navigator.clipboard.writeText(fullText);
                              setEmailCopied(true);
                              setTimeout(() => setEmailCopied(false), 2500);
                            }}
                            className={`flex items-center gap-1.5 px-3.5 py-2.5 rounded-xl text-[13px] font-semibold transition-all shadow-sm ${
                              emailCopied
                                ? 'bg-emerald-600 text-white'
                                : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                            }`}
                          >
                            <span className="material-symbols-outlined text-[17px]">{emailCopied ? 'check' : 'content_copy'}</span>
                            {emailCopied ? 'Copied Full Email!' : 'Copy'}
                          </button>

                          <button
                            onClick={handleGenerateEmail}
                            disabled={emailGenerating}
                            className="flex items-center gap-1.5 px-3.5 py-2.5 rounded-xl bg-gray-100 text-gray-700 hover:bg-gray-200 text-[13px] font-semibold transition-colors disabled:opacity-50"
                          >
                            <span className={`material-symbols-outlined text-[17px] ${emailGenerating ? 'animate-spin' : ''}`}>
                              {emailGenerating ? 'progress_activity' : 'refresh'}
                            </span>
                            Regenerate
                          </button>

                          <button
                            onClick={handleGenerateFollowup}
                            disabled={emailGenerating}
                            className="flex items-center gap-1.5 px-3.5 py-2.5 rounded-xl bg-amber-50 text-amber-800 hover:bg-amber-100 text-[13px] font-semibold transition-colors border border-amber-200 disabled:opacity-50"
                          >
                            <span className="material-symbols-outlined text-[17px]">mark_email_unread</span>
                            Follow-up Nudge
                          </button>
                        </div>

                        {/* Optional Manual Email Client Fallback */}
                        {contacts.primary_email && (
                          <a
                            href={`mailto:${contacts.primary_email}?subject=${encodeURIComponent(emailSubject)}&body=${encodeURIComponent(emailBody)}`}
                            target="_blank"
                            rel="noreferrer"
                            className="flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-gray-50 text-gray-600 hover:bg-gray-100 text-[12px] font-semibold transition-colors border border-gray-200"
                            title="Open in your default mail app"
                          >
                            <span className="material-symbols-outlined text-[15px]">open_in_new</span>
                            Open in Email Client
                          </a>
                        )}
                      </div>
                    </div>
                  )}

                </motion.div>
              )}

              {/* ── Email History ──────────────────────────────────────── */}
              {activeTab === 'Email History' && (
                <motion.div key="eh" className="bg-white rounded-2xl p-6 border border-outline-variant soft-shadow space-y-4"
                  initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}>
                  
                  <div className="flex items-center justify-between border-b border-gray-100 pb-3.5">
                    <div className="flex items-center gap-2.5">
                      <div className="w-8 h-8 rounded-xl bg-purple-50 text-purple-600 flex items-center justify-center">
                        <span className="material-symbols-outlined text-[19px]">history</span>
                      </div>
                      <div>
                        <h3 className="text-[15px] font-bold text-on-surface">Email Communication History</h3>
                        <p className="text-[11.5px] text-gray-500">Structured timeline of generated cold outreach, follow-ups & counter-offers</p>
                      </div>
                    </div>
                    <button
                      onClick={fetchEmailHistory}
                      disabled={loadingHistory}
                      className="p-1.5 rounded-lg text-gray-400 hover:text-gray-600 hover:bg-gray-100 transition-colors"
                      title="Refresh History"
                    >
                      <span className={`material-symbols-outlined text-[18px] ${loadingHistory ? 'animate-spin' : ''}`}>refresh</span>
                    </button>
                  </div>

                  {loadingHistory && emailHistory.length === 0 ? (
                    <div className="py-12 text-center text-gray-400">
                      <span className="material-symbols-outlined text-3xl animate-spin text-purple-500 mb-2 block">sync</span>
                      <p className="text-[13px] font-medium text-gray-600">Loading email history...</p>
                    </div>
                  ) : emailHistory.length === 0 ? (
                    <div className="py-12 text-center text-gray-400 bg-gray-50/50 rounded-xl border border-dashed border-gray-200">
                      <span className="material-symbols-outlined text-4xl mb-2 text-gray-300 block">mail</span>
                      <p className="text-[14px] font-semibold text-gray-700">No Emails Logged Yet</p>
                      <p className="text-[12px] text-gray-400 max-w-sm mx-auto mt-1">
                        Outreach, follow-ups, and negotiation counter-offers generated for {client.name} will automatically be logged here.
                      </p>
                    </div>
                  ) : (
                    <div className="space-y-3">
                      {emailHistory.map((item) => {
                        const badgeStyle = item.email_type === 'outreach'
                          ? 'bg-green-100 text-green-800 border-green-200'
                          : item.email_type === 'followup'
                          ? 'bg-purple-100 text-purple-800 border-purple-200'
                          : 'bg-amber-100 text-amber-800 border-amber-200';

                        const typeLabel = item.email_type === 'outreach'
                          ? 'Cold Outreach'
                          : item.email_type === 'followup'
                          ? 'Follow-up'
                          : 'Negotiation Reply';

                        const formattedDate = new Date(item.created_at).toLocaleString('en-US', {
                          month: 'short', day: 'numeric', year: 'numeric',
                          hour: 'numeric', minute: '2-digit'
                        });

                        return (
                          <div
                            key={item.id}
                            onClick={() => setSelectedHistoryEmail(item)}
                            className="group p-4 rounded-xl border border-gray-200 hover:border-blue-400 hover:shadow-md bg-white hover:bg-blue-50/30 transition-all cursor-pointer flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3"
                          >
                            <div className="space-y-1 min-w-0 flex-1">
                              <div className="flex items-center gap-2 flex-wrap">
                                <span className="font-bold text-[13.5px] text-gray-900 group-hover:text-blue-700 transition-colors">
                                  {item.label}
                                </span>
                                <span className={`px-2 py-0.5 rounded-md text-[10.5px] font-bold border ${badgeStyle}`}>
                                  {typeLabel}
                                </span>
                                <span className="text-[11px] text-gray-400 ml-auto sm:ml-0">
                                  {formattedDate}
                                </span>
                              </div>
                              <p className="text-[13px] font-semibold text-gray-800 truncate">
                                {item.subject || 'No Subject'}
                              </p>
                              <p className="text-[12px] text-gray-500 line-clamp-1 italic">
                                "{item.body.replace(/\n+/g, ' ')}"
                              </p>
                            </div>
                            <button className="flex items-center gap-1 px-3 py-1.5 rounded-lg bg-gray-100 group-hover:bg-blue-600 group-hover:text-white text-gray-700 text-[12px] font-semibold transition-all shrink-0">
                              <span>View</span>
                              <span className="material-symbols-outlined text-[15px]">open_in_new</span>
                            </button>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </motion.div>
              )}

            </AnimatePresence>
          </div>

          {/* Right: sidebar */}
          <div className="lg:col-span-5 flex flex-col gap-4">

            {/* Quick Actions */}
            <motion.div className="bg-white rounded-2xl border border-outline-variant soft-shadow"
              initial={{ opacity: 0, x: 12 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.1 }}>
              <div className="px-4 py-3.5 border-b border-gray-100 flex items-center gap-2">
                <span className="material-symbols-outlined text-primary text-[17px]">bolt</span>
                <h3 className="text-[14px] font-semibold text-on-surface">Quick Contact</h3>
              </div>
              <div className="p-4 flex flex-col gap-2.5">
                {/* Score + Status */}
                <div className="grid grid-cols-2 gap-2">
                  <div className="bg-gray-50 rounded-xl p-3 border border-gray-100">
                    <p className="text-[10px] text-gray-400 font-semibold uppercase tracking-wider mb-0.5">Trust Score</p>
                    <p className="text-[20px] font-bold text-gray-800">{score}<span className="text-[12px] text-gray-400 font-normal">/100</span></p>
                  </div>
                  <div className="bg-gray-50 rounded-xl p-3 border border-gray-100">
                    <p className="text-[10px] text-gray-400 font-semibold uppercase tracking-wider mb-0.5">Status</p>
                    <p className="text-[15px] font-bold text-blue-600">{client.status || 'Pending'}</p>
                  </div>
                </div>

                {/* Direct links */}
                {domain && (
                  <a href={client.website?.startsWith('http') ? client.website : `https://${client.website}`}
                    target="_blank" rel="noreferrer"
                    className="flex items-center gap-2 px-3 py-2.5 rounded-xl bg-blue-50 text-blue-700 hover:bg-blue-100 transition-colors text-[13px] font-medium">
                    <span className="material-symbols-outlined text-[17px]">open_in_new</span>
                    Visit {domain}
                  </a>
                )}
                <button onClick={() => setActiveTab('Contact Info')}
                  className="flex items-center gap-2 px-3 py-2.5 rounded-xl bg-primary text-white hover:bg-primary/90 transition-colors text-[13px] font-semibold justify-center">
                  <span className="material-symbols-outlined text-[17px]">contacts</span>
                  Find Contact Info
                </button>
                <button onClick={() => { setActiveTab('Outreach Email'); if (!emailBody && !emailGenerating) handleGenerateEmail(); }}
                  className="flex items-center gap-2 px-3 py-2.5 rounded-xl bg-gradient-to-r from-blue-600 to-indigo-600 text-white hover:opacity-95 transition-all text-[13px] font-semibold justify-center shadow-sm">
                  <span className="material-symbols-outlined text-[17px]">auto_awesome</span>
                  Generate Outreach Email
                </button>
              </div>
            </motion.div>

            {/* Action Items */}
            <motion.div className="bg-white rounded-2xl border border-outline-variant soft-shadow"
              initial={{ opacity: 0, x: 12 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.15 }}>
              <div className="px-4 py-3.5 border-b border-gray-100 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="material-symbols-outlined text-primary text-[17px]">checklist</span>
                  <h3 className="text-[14px] font-semibold text-on-surface">Action Items</h3>
                </div>
                <span className="text-[11px] font-semibold text-gray-500 bg-gray-100 px-2 py-0.5 rounded-lg">
                  {doneCount}/{tasks.length}
                </span>
              </div>
              <div className="p-2">
                {tasks.map((task, i) => (
                  <label key={i} className="flex items-center gap-3 px-3 py-2.5 hover:bg-gray-50 rounded-xl cursor-pointer transition-colors">
                    <input type="checkbox" checked={task.done} onChange={() => toggleTask(i)}
                      className="w-4 h-4 rounded text-primary cursor-pointer" />
                    <span className={`text-[13px] transition-colors ${task.done ? 'line-through text-gray-400' : 'text-gray-700'}`}>
                      {task.label}
                    </span>
                  </label>
                ))}
              </div>
            </motion.div>
          </div>
        </div>
      </div>

      {/* ── Email Detail Popup Modal ────────────────────────────────────── */}
      <AnimatePresence>
        {selectedHistoryEmail && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
            <motion.div
              initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
              onClick={() => setSelectedHistoryEmail(null)}
              className="absolute inset-0 bg-slate-900/40 backdrop-blur-sm"
            />
            <motion.div
              initial={{ scale: 0.95, opacity: 0, y: 15 }}
              animate={{ scale: 1, opacity: 1, y: 0 }}
              exit={{ scale: 0.95, opacity: 0, y: 15 }}
              className="relative bg-white rounded-3xl shadow-2xl border border-gray-100 w-full max-w-2xl overflow-hidden z-10 flex flex-col max-h-[90vh]"
            >
              {/* Header */}
              <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between bg-gray-50/50">
                <div className="flex items-center gap-2.5">
                  <div className="w-9 h-9 rounded-xl bg-blue-100 text-blue-600 flex items-center justify-center font-bold text-[14px]">
                    <span className="material-symbols-outlined text-[20px]">drafts</span>
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <h3 className="text-[16px] font-bold text-gray-900">{selectedHistoryEmail.label}</h3>
                      <span className={`px-2 py-0.5 rounded-md text-[10.5px] font-bold border ${
                        selectedHistoryEmail.email_type === 'outreach'
                          ? 'bg-green-100 text-green-800 border-green-200'
                          : selectedHistoryEmail.email_type === 'followup'
                          ? 'bg-purple-100 text-purple-800 border-purple-200'
                          : 'bg-amber-100 text-amber-800 border-amber-200'
                      }`}>
                        {selectedHistoryEmail.email_type === 'outreach' ? 'Cold Outreach' : selectedHistoryEmail.email_type === 'followup' ? 'Follow-up' : 'Negotiation Reply'}
                      </span>
                    </div>
                    <p className="text-[11.5px] text-gray-400">
                      Logged on {new Date(selectedHistoryEmail.created_at).toLocaleString()}
                    </p>
                  </div>
                </div>
                <button
                  onClick={() => setSelectedHistoryEmail(null)}
                  className="p-1.5 text-gray-400 hover:text-gray-600 rounded-lg hover:bg-gray-200/60 transition-colors"
                >
                  <span className="material-symbols-outlined">close</span>
                </button>
              </div>

              {/* Modal Body Content */}
              <div className="p-6 overflow-y-auto space-y-4 custom-scrollbar">
                {selectedHistoryEmail.recipient_email && (
                  <div className="flex items-center gap-2 text-[12px] text-gray-600 bg-blue-50/50 p-2.5 rounded-xl border border-blue-100">
                    <span className="font-semibold text-blue-900">Recipient:</span>
                    <span className="font-medium text-blue-700">{selectedHistoryEmail.recipient_email}</span>
                  </div>
                )}

                <div className="space-y-1">
                  <label className="text-[11px] font-bold uppercase text-gray-400 tracking-wider">Subject Line</label>
                  <div className="p-3 bg-gray-50 rounded-xl border border-gray-200 text-[14px] font-bold text-gray-800">
                    {selectedHistoryEmail.subject || 'No Subject'}
                  </div>
                </div>

                <div className="space-y-1">
                  <label className="text-[11px] font-bold uppercase text-gray-400 tracking-wider">Email Content</label>
                  <div className="p-4 bg-gray-50 rounded-xl border border-gray-200 text-[13.5px] text-gray-800 leading-relaxed whitespace-pre-wrap font-sans">
                    {selectedHistoryEmail.body}
                  </div>
                </div>
              </div>

              {/* Modal Footer */}
              <div className="px-6 py-3.5 border-t border-gray-100 bg-gray-50/50 flex items-center justify-between">
                <button
                  onClick={() => {
                    const textToCopy = `Subject: ${selectedHistoryEmail.subject || ''}\n\n${selectedHistoryEmail.body}`;
                    navigator.clipboard.writeText(textToCopy);
                    setHistoryCopied(true);
                    setTimeout(() => setHistoryCopied(false), 2000);
                  }}
                  className="flex items-center gap-1.5 px-4 py-2 rounded-xl bg-blue-600 text-white hover:bg-blue-700 text-[12.5px] font-semibold shadow-sm transition-all"
                >
                  <span className="material-symbols-outlined text-[16px]">
                    {historyCopied ? 'check' : 'content_copy'}
                  </span>
                  {historyCopied ? 'Copied to Clipboard!' : 'Copy Full Email'}
                </button>
                <button
                  onClick={() => setSelectedHistoryEmail(null)}
                  className="px-4 py-2 rounded-xl bg-gray-200 text-gray-700 hover:bg-gray-300 text-[12.5px] font-semibold transition-all"
                >
                  Close
                </button>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>

      {/* ── Creative Email Sent Animated Glassmorphism Modal ────────────────────── */}
      <AnimatePresence>
        {showSentModal && sentModalData && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={() => setShowSentModal(false)}
              className="absolute inset-0 bg-slate-900/40 backdrop-blur-md"
            />
            <motion.div
              initial={{ scale: 0.8, opacity: 0, y: 30 }}
              animate={{ scale: 1, opacity: 1, y: 0 }}
              exit={{ scale: 0.8, opacity: 0, y: 30 }}
              transition={{ type: 'spring', stiffness: 350, damping: 25 }}
              className="relative bg-white/95 backdrop-blur-xl rounded-3xl shadow-2xl border border-white/60 p-8 max-w-md w-full text-center overflow-hidden z-10 flex flex-col items-center"
            >
              {/* Glowing Animated Icon Badge */}
              <motion.div
                initial={{ scale: 0, rotate: -45 }}
                animate={{ scale: 1, rotate: 0 }}
                transition={{ delay: 0.15, type: 'spring', stiffness: 400, damping: 20 }}
                className="w-20 h-20 rounded-3xl bg-gradient-to-tr from-emerald-500 to-teal-400 text-white flex items-center justify-center shadow-lg shadow-emerald-500/30 mb-5 relative"
              >
                <span className="material-symbols-outlined text-[42px]">mark_email_read</span>
                <motion.span
                  animate={{ scale: [1, 1.4, 1], opacity: [0.6, 0, 0.6] }}
                  transition={{ repeat: Infinity, duration: 2 }}
                  className="absolute inset-0 rounded-3xl border-2 border-emerald-400"
                />
              </motion.div>

              <h3 className="text-2xl font-bold text-gray-900 tracking-tight">Email Delivered!</h3>
              <p className="text-[13px] text-gray-500 mt-1 max-w-xs leading-relaxed">
                Your cold outreach email was successfully dispatched via Gmail SMTP to:
              </p>

              <div className="my-4 w-full p-3.5 bg-gray-50/80 rounded-2xl border border-gray-100 text-left space-y-1">
                <div className="flex items-center justify-between text-[11px] text-gray-400 font-semibold uppercase tracking-wider">
                  <span>Recipient</span>
                  <span className="text-emerald-600 font-bold bg-emerald-50 px-2 py-0.5 rounded-md border border-emerald-100">
                    {sentModalData.label} Logged
                  </span>
                </div>
                <p className="text-[13px] font-bold text-blue-700 truncate">{sentModalData.recipient}</p>
                <p className="text-[12px] font-medium text-gray-700 truncate pt-1 border-t border-gray-100">
                  Subject: {sentModalData.subject}
                </p>
              </div>

              <div className="flex items-center gap-2 text-[12px] text-emerald-700 font-semibold bg-emerald-50 px-3 py-1.5 rounded-xl border border-emerald-100 mb-6">
                <span className="material-symbols-outlined text-[16px]">check_circle</span>
                <span>Saved to Client Email History Timeline</span>
              </div>

              <button
                onClick={() => setShowSentModal(false)}
                className="w-full py-3 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-700 hover:to-indigo-700 text-white font-bold rounded-2xl shadow-md shadow-blue-500/25 transition-all text-[14px] cursor-pointer"
              >
                Awesome, Got It!
              </button>
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </div>
  );
}
