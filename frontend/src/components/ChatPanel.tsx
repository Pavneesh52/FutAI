import { useState, useRef, useEffect, type FormEvent, type KeyboardEvent } from 'react'
import ReactMarkdown from 'react-markdown'
import {
  Send,
  Bot,
  User,
  Sparkles,
  AlertTriangle,
  RotateCcw,
  Loader2,
  HelpCircle,
  CheckCircle,
} from 'lucide-react'
import { postAnalysis, type AnalysisResult } from '../api/client'
import { EvidenceViewer } from './EvidenceViewer'

interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  result?: AnalysisResult
  error?: string
  isLoading?: boolean
}

interface ChatPanelProps {
  matchId?: number
  homeTeamName?: string
  awayTeamName?: string
}

export function ChatPanel({ matchId, homeTeamName, awayTeamName }: ChatPanelProps) {
  const [messages, setMessages] = useState<Message[]>([])
  const [inputQuery, setInputQuery] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  const starterQuestions = [
    homeTeamName && awayTeamName
      ? `What was the final score and xG comparison between ${homeTeamName} and ${awayTeamName}?`
      : 'What was the final score and xG comparison?',
    'Which team pressed more aggressively, and what were their PPDA values?',
    'How many total shots and passes did each team record?',
    'What were the key territorial and tactical dominance indicators?',
  ]

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  const handleSendQuery = async (queryText: string) => {
    const trimmed = queryText.trim()
    if (!trimmed || isSubmitting) return

    const userMsgId = `user-${Date.now()}`
    const botMsgId = `assistant-${Date.now()}`

    const userMsg: Message = {
      id: userMsgId,
      role: 'user',
      content: trimmed,
    }

    const botLoadingMsg: Message = {
      id: botMsgId,
      role: 'assistant',
      content: '',
      isLoading: true,
    }

    setMessages((prev) => [...prev, userMsg, botLoadingMsg])
    setInputQuery('')
    setIsSubmitting(true)

    try {
      const result = await postAnalysis({
        query: trimmed,
        match_id: matchId ?? null,
      })

      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === botMsgId
            ? {
                ...msg,
                isLoading: false,
                content: result.answer_markdown,
                result,
              }
            : msg,
        ),
      )
    } catch (err: any) {
      const errorMessage =
        err?.message || 'Failed to analyze query. Please verify backend service connectivity.'
      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === botMsgId
            ? {
                ...msg,
                isLoading: false,
                content: '',
                error: errorMessage,
              }
            : msg,
        ),
      )
    } finally {
      setIsSubmitting(false)
    }
  }

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault()
    handleSendQuery(inputQuery)
  }

  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSendQuery(inputQuery)
    }
  }

  const handleRetry = (botMsgId: string) => {
    // Find the preceding user message
    const msgIndex = messages.findIndex((m) => m.id === botMsgId)
    if (msgIndex > 0 && messages[msgIndex - 1].role === 'user') {
      const userText = messages[msgIndex - 1].content
      // Remove the failed bot message
      setMessages((prev) => prev.filter((m) => m.id !== botMsgId))
      handleSendQuery(userText)
    }
  }

  return (
    <div className="flex flex-col h-[640px] rounded-2xl border border-slate-800 bg-slate-900/60 backdrop-blur-md shadow-2xl overflow-hidden">
      {/* Panel header */}
      <div className="px-5 py-4 border-b border-slate-800 bg-slate-950/40 flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <div className="p-2 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 shadow-sm">
            <Bot className="w-5 h-5" />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-white flex items-center gap-2">
              Football Analyst Agent
              <span className="inline-flex items-center gap-1 text-[10px] font-medium px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                <CheckCircle className="w-3 h-3" /> Grounded R1/R2
              </span>
            </h3>
            <p className="text-[11px] text-slate-400">
              Deterministic answers backed by tool executions and verified database metrics
            </p>
          </div>
        </div>

        {messages.length > 0 && (
          <button
            type="button"
            onClick={() => setMessages([])}
            className="text-xs text-slate-400 hover:text-slate-200 px-2 py-1 rounded hover:bg-slate-800 transition-colors"
            title="Clear conversation"
          >
            Clear
          </button>
        )}
      </div>

      {/* Messages Scroll Area */}
      <div className="flex-1 p-5 overflow-y-auto space-y-4">
        {messages.length === 0 ? (
          <div className="h-full flex flex-col justify-center items-center text-center px-4 py-8">
            <div className="p-3 rounded-2xl bg-slate-800/60 border border-slate-700/50 mb-3 text-emerald-400">
              <Sparkles className="w-6 h-6" />
            </div>
            <h4 className="text-sm font-semibold text-slate-200">Ask the AI Match Analyst</h4>
            <p className="text-xs text-slate-400 mt-1 max-w-sm mb-6">
              Ask any tactical, event, or player performance question. Every number is verified
              against actual match data.
            </p>

            {/* Suggested starter questions */}
            <div className="w-full max-w-md space-y-2">
              <p className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider text-left flex items-center gap-1">
                <HelpCircle className="w-3.5 h-3.5" /> Suggested Questions
              </p>
              <div className="grid grid-cols-1 gap-2">
                {starterQuestions.map((q, idx) => (
                  <button
                    key={idx}
                    type="button"
                    onClick={() => handleSendQuery(q)}
                    className="w-full text-left p-2.5 rounded-xl border border-slate-800 bg-slate-950/50 hover:bg-slate-800/70 hover:border-emerald-500/40 text-xs text-slate-300 hover:text-white transition-all duration-150 cursor-pointer"
                  >
                    "{q}"
                  </button>
                ))}
              </div>
            </div>
          </div>
        ) : (
          messages.map((msg) => (
            <div
              key={msg.id}
              className={`flex gap-3 ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
            >
              {msg.role === 'assistant' && (
                <div className="w-7 h-7 rounded-lg bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center text-emerald-400 shrink-0 mt-0.5">
                  <Bot className="w-4 h-4" />
                </div>
              )}

              <div
                className={`max-w-[85%] rounded-2xl px-4 py-3 text-xs leading-relaxed ${
                  msg.role === 'user'
                    ? 'bg-emerald-600 text-white rounded-br-none shadow-md'
                    : 'bg-slate-950/80 border border-slate-800 text-slate-200 rounded-bl-none shadow-lg'
                }`}
              >
                {msg.role === 'user' ? (
                  <p className="font-medium whitespace-pre-wrap">{msg.content}</p>
                ) : msg.isLoading ? (
                  <div className="flex items-center gap-2.5 py-1 text-slate-400">
                    <Loader2 className="w-4 h-4 animate-spin text-emerald-400" />
                    <span>Analyzing match data with deterministic tools...</span>
                  </div>
                ) : msg.error ? (
                  <div className="space-y-2 text-rose-300">
                    <div className="flex items-center gap-2">
                      <AlertTriangle className="w-4 h-4 shrink-0 text-rose-400" />
                      <span className="font-semibold text-rose-200">Analysis Error</span>
                    </div>
                    <p className="text-xs text-rose-300/90">{msg.error}</p>
                    <button
                      type="button"
                      onClick={() => handleRetry(msg.id)}
                      className="mt-1 inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-rose-500/20 hover:bg-rose-500/30 text-rose-200 border border-rose-500/30 transition-colors cursor-pointer text-[11px]"
                    >
                      <RotateCcw className="w-3 h-3" /> Retry query
                    </button>
                  </div>
                ) : (
                  <div className="space-y-2">
                    {/* Metadata header */}
                    {msg.result && (
                      <div className="flex items-center gap-2 pb-2 border-b border-slate-800/80 text-[10px] text-slate-400">
                        <span className="px-1.5 py-0.5 rounded bg-slate-800 text-slate-300 font-medium">
                          {msg.result.query_type}
                        </span>
                        <span>Confidence: {Math.round(msg.result.confidence * 100)}%</span>
                        {msg.result.degraded && (
                          <span className="px-1.5 py-0.5 rounded bg-amber-500/20 text-amber-300 border border-amber-500/30">
                            Degraded mode
                          </span>
                        )}
                      </div>
                    )}

                    {/* Markdown Answer */}
                    <div className="prose prose-invert prose-xs max-w-none text-slate-200 leading-relaxed space-y-2 font-normal">
                      <ReactMarkdown>{msg.content}</ReactMarkdown>
                    </div>

                    {/* Evidence Drawer */}
                    {msg.result?.evidence && msg.result.evidence.length > 0 && (
                      <EvidenceViewer evidence={msg.result.evidence} />
                    )}
                  </div>
                )}
              </div>

              {msg.role === 'user' && (
                <div className="w-7 h-7 rounded-lg bg-slate-800 border border-slate-700 flex items-center justify-center text-slate-300 shrink-0 mt-0.5">
                  <User className="w-4 h-4" />
                </div>
              )}
            </div>
          ))
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input area */}
      <form onSubmit={handleSubmit} className="p-4 border-t border-slate-800 bg-slate-950/80">
        <div className="relative flex items-center">
          <input
            type="text"
            value={inputQuery}
            onChange={(e) => setInputQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={
              matchId
                ? 'Ask about goals, xG, PPDA, shots, players, or match events...'
                : 'Ask any football analysis question...'
            }
            disabled={isSubmitting}
            className="w-full pl-4 pr-12 py-3 text-xs bg-slate-900 border border-slate-800 rounded-xl text-slate-100 placeholder-slate-500 focus:outline-none focus:border-emerald-500/70 focus:ring-1 focus:ring-emerald-500/50 transition-all disabled:opacity-50"
          />
          <button
            type="submit"
            disabled={isSubmitting || !inputQuery.trim()}
            className="absolute right-2 p-2 rounded-lg bg-emerald-500 hover:bg-emerald-400 text-slate-950 disabled:opacity-30 disabled:hover:bg-emerald-500 transition-all cursor-pointer disabled:cursor-not-allowed shadow-md"
            title="Send query"
          >
            {isSubmitting ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Send className="w-4 h-4" />
            )}
          </button>
        </div>
      </form>
    </div>
  )
}
