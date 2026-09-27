export interface paths {
  '/health': {
    parameters: {
      query?: never
      header?: never
      path?: never
      cookie?: never
    }
    /**
     * Liveness check plus dependency status
     * @description Report whether the API is up, and whether its database is reachable.
     *
     *     Always returns HTTP 200 while the process is serving: a database that is down or
     *     not yet configured is reported in the body (rule R5 -- degrade, don't crash).
     */
    get: operations['health_health_get']
    put?: never
    post?: never
    delete?: never
    options?: never
    head?: never
    patch?: never
    trace?: never
  }
  '/matches': {
    parameters: {
      query?: never
      header?: never
      path?: never
      cookie?: never
    }
    /**
     * List matches
     * @description All ingested matches, most recent first.
     */
    get: operations['list_matches_matches_get']
    put?: never
    post?: never
    delete?: never
    options?: never
    head?: never
    patch?: never
    trace?: never
  }
  '/matches/{match_id}': {
    parameters: {
      query?: never
      header?: never
      path?: never
      cookie?: never
    }
    /**
     * One match
     * @description A match with the counts that tell you what data exists for it.
     */
    get: operations['get_match_matches__match_id__get']
    put?: never
    post?: never
    delete?: never
    options?: never
    head?: never
    patch?: never
    trace?: never
  }
  '/matches/{match_id}/events': {
    parameters: {
      query?: never
      header?: never
      path?: never
      cookie?: never
    }
    /**
     * A match's events
     * @description Events in match order, optionally filtered by normalised type.
     */
    get: operations['get_events_matches__match_id__events_get']
    put?: never
    post?: never
    delete?: never
    options?: never
    head?: never
    patch?: never
    trace?: never
  }
  '/matches/{match_id}/players': {
    parameters: {
      query?: never
      header?: never
      path?: never
      cookie?: never
    }
    /**
     * Per-player aggregates for a match
     * @description Per-player aggregates, most minutes first. Unused substitutes appear with 0 minutes.
     */
    get: operations['get_players_matches__match_id__players_get']
    put?: never
    post?: never
    delete?: never
    options?: never
    head?: never
    patch?: never
    trace?: never
  }
  '/matches/{match_id}/stats': {
    parameters: {
      query?: never
      header?: never
      path?: never
      cookie?: never
    }
    /**
     * Per-team match statistics
     * @description Per-team match aggregates (possession %, xG, PPDA, field tilt, shots, passes).
     */
    get: operations['get_team_stats_matches__match_id__stats_get']
    put?: never
    post?: never
    delete?: never
    options?: never
    head?: never
    patch?: never
    trace?: never
  }
  '/analysis': {
    parameters: {
      query?: never
      header?: never
      path?: never
      cookie?: never
    }
    get?: never
    put?: never
    /**
     * Analyze Query
     * @description Analyze a football question using deterministic tools and Grok.
     */
    post: operations['analyze_query_analysis_post']
    delete?: never
    options?: never
    head?: never
    patch?: never
    trace?: never
  }
}
export type webhooks = Record<string, never>
export interface components {
  schemas: {
    /**
     * AnalysisRequest
     * @description Payload for POST /analysis.
     */
    AnalysisRequest: {
      /** Query */
      query: string
      /** Match Id */
      match_id?: number | null
    }
    /**
     * AnalysisResult
     * @description Response contract for POST /analysis and base for specialized queries.
     */
    AnalysisResult: {
      /** Run Id */
      run_id: string
      /**
       * Query Type
       * @enum {string}
       */
      query_type: 'simple_stat' | 'player' | 'tactical' | 'comparison' | 'report'
      /** Answer Markdown */
      answer_markdown: string
      /** Evidence */
      evidence?: components['schemas']['EvidenceItem'][]
      /** Sources */
      sources?: components['schemas']['SourceItem'][]
      /**
       * Confidence
       * @default 1
       */
      confidence: number
      /**
       * Degraded
       * @default false
       */
      degraded: boolean
      /**
       * Retry Count
       * @default 0
       */
      retry_count: number
    }
    /**
     * EvidenceItem
     * @description One resolved evidence_ref, rendered in the UI's Evidence list.
     */
    EvidenceItem: {
      /** Ref */
      ref: string
      /** Label */
      label: string
      /** Value */
      value?: unknown
    }
    /** HTTPValidationError */
    HTTPValidationError: {
      /** Detail */
      detail?: components['schemas']['ValidationError'][]
    }
    /**
     * HealthResponse
     * @description Result of `GET /health`.
     */
    HealthResponse: {
      /**
       * Status
       * @description `degraded` when a required dependency is unreachable; the process is still serving.
       * @enum {string}
       */
      status: 'ok' | 'degraded'
      /**
       * Db
       * @description Database probe result: `ok`, `unavailable`, or `not_configured`.
       * @enum {string}
       */
      db: 'ok' | 'unavailable' | 'not_configured'
    }
    /**
     * MatchDetail
     * @description `GET /matches/{id}`: a summary plus what the match actually contains.
     */
    MatchDetail: {
      /** Id */
      id: number
      home_team: components['schemas']['TeamSummary']
      away_team: components['schemas']['TeamSummary']
      /** Competition */
      competition: string
      /** Season */
      season: string
      /**
       * Match Date
       * Format: date
       */
      match_date: string
      /**
       * Home Score
       * @description NULL if not played in the source.
       */
      home_score?: number | null
      /** Away Score */
      away_score?: number | null
      /**
       * Event Count
       * @description Number of ingested events.
       */
      event_count: number
      /**
       * Has Stats
       * @description True once team_match_stats rows exist for this match.
       */
      has_stats: boolean
    }
    /**
     * MatchEvent
     * @description A single event, with our own surrogate `id` (the source id is a UUID).
     */
    MatchEvent: {
      /** Id */
      id: number
      /** Match Id */
      match_id: number
      /** Minute */
      minute: number
      /** Second */
      second: number
      /** Event Type */
      event_type: string
      /** Team Id */
      team_id: number
      /** Player Id */
      player_id?: number | null
      /** X */
      x?: number | null
      /** Y */
      y?: number | null
      /** Outcome */
      outcome?: string | null
      /** Xg */
      xg?: number | null
      /** Related Event Id */
      related_event_id?: number | null
      /** Possession Id */
      possession_id?: number | null
    }
    /**
     * MatchSummary
     * @description One row of `GET /matches`.
     */
    MatchSummary: {
      /** Id */
      id: number
      home_team: components['schemas']['TeamSummary']
      away_team: components['schemas']['TeamSummary']
      /** Competition */
      competition: string
      /** Season */
      season: string
      /**
       * Match Date
       * Format: date
       */
      match_date: string
      /**
       * Home Score
       * @description NULL if not played in the source.
       */
      home_score?: number | null
      /** Away Score */
      away_score?: number | null
    }
    /**
     * PlayerMatchStats
     * @description Aggregated player performance in one match.
     */
    PlayerMatchStats: {
      /** Match Id */
      match_id: number
      /** Player Id */
      player_id: number
      /** Player Name */
      player_name: string
      /** Team Id */
      team_id: number
      /** Minutes Played */
      minutes_played?: number | null
      /** Goals */
      goals?: number | null
      /** Assists */
      assists?: number | null
      /** Xg */
      xg?: number | null
      /** Xa */
      xa?: number | null
      /** Passes */
      passes?: number | null
      /** Pass Accuracy */
      pass_accuracy?: number | null
      /** Shots */
      shots?: number | null
      /** Tackles */
      tackles?: number | null
      /** Position Played */
      position_played?: string | null
    }
    /**
     * SourceItem
     * @description RAG citations only (Phase 7).
     */
    SourceItem: {
      /** Title */
      title: string
      /** Url */
      url: string
    }
    /**
     * TeamMatchStats
     * @description Aggregated team performance in one match.
     */
    TeamMatchStats: {
      /** Match Id */
      match_id: number
      /** Team Id */
      team_id: number
      /** Team Name */
      team_name: string
      /** Possession Pct */
      possession_pct?: number | null
      /** Xg */
      xg?: number | null
      /** Shots */
      shots?: number | null
      /** Shots On Target */
      shots_on_target?: number | null
      /** Passes */
      passes?: number | null
      /** Pass Accuracy */
      pass_accuracy?: number | null
      /** Ppda */
      ppda?: number | null
      /** Field Tilt */
      field_tilt?: number | null
      /** Formation */
      formation?: string | null
    }
    /**
     * TeamSummary
     * @description A team, as embedded in a match summary.
     */
    TeamSummary: {
      /** Id */
      id: number
      /** Name */
      name: string
      /** Country */
      country?: string | null
    }
    /** ValidationError */
    ValidationError: {
      /** Location */
      loc: (string | number)[]
      /** Message */
      msg: string
      /** Error Type */
      type: string
      /** Input */
      input?: unknown
      /** Context */
      ctx?: Record<string, never>
    }
  }
  responses: never
  parameters: never
  requestBodies: never
  headers: never
  pathItems: never
}
export type $defs = Record<string, never>
export interface operations {
  health_health_get: {
    parameters: {
      query?: never
      header?: never
      path?: never
      cookie?: never
    }
    requestBody?: never
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['HealthResponse']
        }
      }
    }
  }
  list_matches_matches_get: {
    parameters: {
      query?: never
      header?: never
      path?: never
      cookie?: never
    }
    requestBody?: never
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['MatchSummary'][]
        }
      }
    }
  }
  get_match_matches__match_id__get: {
    parameters: {
      query?: never
      header?: never
      path: {
        match_id: number
      }
      cookie?: never
    }
    requestBody?: never
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['MatchDetail']
        }
      }
      /** @description Validation Error */
      422: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['HTTPValidationError']
        }
      }
    }
  }
  get_events_matches__match_id__events_get: {
    parameters: {
      query?: {
        /** @description Normalised event type, e.g. `shot`, `pass`, `tackle`. */
        event_type?: string | null
      }
      header?: never
      path: {
        match_id: number
      }
      cookie?: never
    }
    requestBody?: never
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['MatchEvent'][]
        }
      }
      /** @description Validation Error */
      422: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['HTTPValidationError']
        }
      }
    }
  }
  get_players_matches__match_id__players_get: {
    parameters: {
      query?: never
      header?: never
      path: {
        match_id: number
      }
      cookie?: never
    }
    requestBody?: never
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['PlayerMatchStats'][]
        }
      }
      /** @description Validation Error */
      422: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['HTTPValidationError']
        }
      }
    }
  }
  get_team_stats_matches__match_id__stats_get: {
    parameters: {
      query?: {
        /** @description Filter by team id; if omitted, returns both teams. */
        team_id?: number | null
      }
      header?: never
      path: {
        match_id: number
      }
      cookie?: never
    }
    requestBody?: never
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['TeamMatchStats'][]
        }
      }
      /** @description Validation Error */
      422: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['HTTPValidationError']
        }
      }
    }
  }
  analyze_query_analysis_post: {
    parameters: {
      query?: never
      header?: never
      path?: never
      cookie?: never
    }
    requestBody: {
      content: {
        'application/json': components['schemas']['AnalysisRequest']
      }
    }
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['AnalysisResult']
        }
      }
      /** @description Validation Error */
      422: {
        headers: {
          [name: string]: unknown
        }
        content: {
          'application/json': components['schemas']['HTTPValidationError']
        }
      }
    }
  }
}
