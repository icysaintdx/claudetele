/**
 * Ollama Adapter — Intercepts Anthropic SDK fetch calls and translates
 * Anthropic Messages API ↔ OpenAI Chat Completions API for Ollama.
 *
 * Handles both streaming (SSE) and non-streaming modes.
 *
 * Usage: Set OLLAMA_BASE_URL=http://localhost:11434 and OLLAMA_MODEL=qwen2.5:14b in .env
 */

// ─── Types ───────────────────────────────────────────────────────────────────

interface AnthropicMessage {
  role: 'user' | 'assistant'
  content: string | AnthropicContentBlock[]
}

interface AnthropicContentBlock {
  type: 'text' | 'tool_use' | 'tool_result' | 'image' | 'thinking'
  text?: string
  id?: string
  name?: string
  input?: unknown
  tool_use_id?: string
  content?: string | AnthropicContentBlock[]
  thinking?: string
  source?: unknown
}

interface AnthropicRequest {
  model: string
  messages: AnthropicMessage[]
  system?: string | Array<{ type: string; text: string }>
  max_tokens: number
  stream?: boolean
  tools?: AnthropicTool[]
  temperature?: number
  top_p?: number
  stop_sequences?: string[]
  thinking?: { type: string; budget_tokens?: number }
  [key: string]: unknown
}

interface AnthropicTool {
  name: string
  description?: string
  input_schema?: unknown
}

interface OpenAIMessage {
  role: 'system' | 'user' | 'assistant' | 'tool'
  content: string | null
  tool_calls?: OpenAIToolCall[]
  tool_call_id?: string
}

interface OpenAIToolCall {
  id: string
  type: 'function'
  function: {
    name: string
    arguments: string
  }
}

interface OpenAITool {
  type: 'function'
  function: {
    name: string
    description?: string
    parameters?: unknown
  }
}

// ─── Conversion: Anthropic → OpenAI ──────────────────────────────────────────

function extractTextFromContent(
  content: string | AnthropicContentBlock[],
): string {
  if (typeof content === 'string') return content
  return content
    .filter((b) => b.type === 'text' && b.text)
    .map((b) => b.text!)
    .join('\n')
}

function convertMessages(
  messages: AnthropicMessage[],
  systemPrompt?: string | Array<{ type: string; text: string }>,
): OpenAIMessage[] {
  const result: OpenAIMessage[] = []

  // System prompt
  if (systemPrompt) {
    const text =
      typeof systemPrompt === 'string'
        ? systemPrompt
        : systemPrompt.map((s) => s.text).join('\n')
    if (text.trim()) {
      result.push({ role: 'system', content: text })
    }
  }

  for (const msg of messages) {
    if (msg.role === 'user') {
      if (typeof msg.content === 'string') {
        result.push({ role: 'user', content: msg.content })
      } else {
        // Check for tool_result blocks
        const toolResults = msg.content.filter(
          (b) => b.type === 'tool_result',
        )
        const otherBlocks = msg.content.filter(
          (b) => b.type !== 'tool_result',
        )

        // Add tool results as tool messages
        for (const tr of toolResults) {
          const resultContent =
            typeof tr.content === 'string'
              ? tr.content
              : tr.content
                ? extractTextFromContent(tr.content)
                : ''
          result.push({
            role: 'tool',
            tool_call_id: tr.tool_use_id || 'unknown',
            content: resultContent || '(empty)',
          })
        }

        // Add other content as user message
        if (otherBlocks.length > 0) {
          const text = extractTextFromContent(otherBlocks)
          if (text.trim()) {
            result.push({ role: 'user', content: text })
          }
        }
      }
    } else if (msg.role === 'assistant') {
      if (typeof msg.content === 'string') {
        result.push({ role: 'assistant', content: msg.content })
      } else {
        // Check for tool_use blocks
        const toolUses = msg.content.filter((b) => b.type === 'tool_use')
        const textContent = extractTextFromContent(msg.content)

        if (toolUses.length > 0) {
          const toolCalls: OpenAIToolCall[] = toolUses.map((tu) => ({
            id: tu.id || `call_${Math.random().toString(36).slice(2)}`,
            type: 'function' as const,
            function: {
              name: tu.name || 'unknown',
              arguments:
                typeof tu.input === 'string'
                  ? tu.input
                  : JSON.stringify(tu.input || {}),
            },
          }))
          result.push({
            role: 'assistant',
            content: textContent || null,
            tool_calls: toolCalls,
          })
        } else {
          result.push({ role: 'assistant', content: textContent })
        }
      }
    }
  }

  return result
}

function convertTools(tools?: AnthropicTool[]): OpenAITool[] | undefined {
  if (!tools || tools.length === 0) return undefined
  return tools.map((t) => ({
    type: 'function' as const,
    function: {
      name: t.name,
      description: t.description,
      parameters: t.input_schema,
    },
  }))
}

// ─── Conversion: OpenAI SSE → Anthropic SSE ──────────────────────────────────

function makeAnthropicSSE(event: string, data: unknown): string {
  return `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`
}

function buildAnthropicStreamFromOpenAI(
  openaiStream: ReadableStream<Uint8Array>,
  model: string,
): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder()
  const decoder = new TextDecoder()
  let buffer = ''
  let sentMessageStart = false
  let contentBlockStarted = false
  let currentToolCallId = ''
  let currentToolName = ''
  let toolCallIndex = -1
  let blockIndex = 0
  let inputTokens = 100 // estimate
  let outputTokens = 0

  return new ReadableStream({
    async start(controller) {
      const reader = openaiStream.getReader()

      try {
        while (true) {
          const { done, value } = await reader.read()
          if (done) break

          buffer += decoder.decode(value, { stream: true })
          const lines = buffer.split('\n')
          buffer = lines.pop() || ''

          for (const line of lines) {
            if (!line.startsWith('data: ')) continue
            const data = line.slice(6).trim()
            if (data === '[DONE]') {
              // End content block if open
              if (contentBlockStarted) {
                controller.enqueue(
                  encoder.encode(
                    makeAnthropicSSE('content_block_stop', {
                      type: 'content_block_stop',
                      index: blockIndex,
                    }),
                  ),
                )
                contentBlockStarted = false
              }
              // message_delta with stop_reason
              controller.enqueue(
                encoder.encode(
                  makeAnthropicSSE('message_delta', {
                    type: 'message_delta',
                    delta: { stop_reason: 'end_turn', stop_sequence: null },
                    usage: { output_tokens: outputTokens },
                  }),
                ),
              )
              // message_stop
              controller.enqueue(
                encoder.encode(
                  makeAnthropicSSE('message_stop', {
                    type: 'message_stop',
                  }),
                ),
              )
              controller.close()
              return
            }

            let chunk: {
              id?: string
              choices?: Array<{
                delta?: {
                  role?: string
                  content?: string | null
                  tool_calls?: Array<{
                    index: number
                    id?: string
                    function?: { name?: string; arguments?: string }
                  }>
                }
                finish_reason?: string | null
              }>
              usage?: { prompt_tokens?: number; completion_tokens?: number }
            }
            try {
              chunk = JSON.parse(data)
            } catch {
              continue
            }

            if (!chunk.choices || chunk.choices.length === 0) continue
            const choice = chunk.choices[0]!
            const delta = choice.delta

            // Send message_start on first chunk
            if (!sentMessageStart) {
              sentMessageStart = true
              controller.enqueue(
                encoder.encode(
                  makeAnthropicSSE('message_start', {
                    type: 'message_start',
                    message: {
                      id: chunk.id || `msg_${Date.now()}`,
                      type: 'message',
                      role: 'assistant',
                      content: [],
                      model: model,
                      stop_reason: null,
                      stop_sequence: null,
                      usage: {
                        input_tokens: inputTokens,
                        output_tokens: 0,
                        cache_creation_input_tokens: 0,
                        cache_read_input_tokens: 0,
                      },
                    },
                  }),
                ),
              )
            }

            // Handle tool calls
            if (delta?.tool_calls && delta.tool_calls.length > 0) {
              for (const tc of delta.tool_calls) {
                if (tc.id && tc.id !== currentToolCallId) {
                  // Close previous block if open
                  if (contentBlockStarted) {
                    controller.enqueue(
                      encoder.encode(
                        makeAnthropicSSE('content_block_stop', {
                          type: 'content_block_stop',
                          index: blockIndex,
                        }),
                      ),
                    )
                    blockIndex++
                  }
                  // New tool call
                  currentToolCallId = tc.id
                  currentToolName = tc.function?.name || ''
                  toolCallIndex = tc.index
                  contentBlockStarted = true
                  controller.enqueue(
                    encoder.encode(
                      makeAnthropicSSE('content_block_start', {
                        type: 'content_block_start',
                        index: blockIndex,
                        content_block: {
                          type: 'tool_use',
                          id: currentToolCallId,
                          name: currentToolName,
                          input: {},
                        },
                      }),
                    ),
                  )
                }

                // Stream tool arguments
                if (tc.function?.arguments) {
                  outputTokens += 1
                  controller.enqueue(
                    encoder.encode(
                      makeAnthropicSSE('content_block_delta', {
                        type: 'content_block_delta',
                        index: blockIndex,
                        delta: {
                          type: 'input_json_delta',
                          partial_json: tc.function.arguments,
                        },
                      }),
                    ),
                  )
                }
              }
              continue
            }

            // Handle text content
            if (delta?.content) {
              if (!contentBlockStarted) {
                contentBlockStarted = true
                controller.enqueue(
                  encoder.encode(
                    makeAnthropicSSE('content_block_start', {
                      type: 'content_block_start',
                      index: blockIndex,
                      content_block: {
                        type: 'text',
                        text: '',
                      },
                    }),
                  ),
                )
              }
              outputTokens += 1
              controller.enqueue(
                encoder.encode(
                  makeAnthropicSSE('content_block_delta', {
                    type: 'content_block_delta',
                    index: blockIndex,
                    delta: {
                      type: 'text_delta',
                      text: delta.content,
                    },
                  }),
                ),
              )
            }

            // Handle finish_reason
            if (choice.finish_reason) {
              if (contentBlockStarted) {
                controller.enqueue(
                  encoder.encode(
                    makeAnthropicSSE('content_block_stop', {
                      type: 'content_block_stop',
                      index: blockIndex,
                    }),
                  ),
                )
                contentBlockStarted = false
              }

              const stopReason =
                choice.finish_reason === 'tool_calls'
                  ? 'tool_use'
                  : choice.finish_reason === 'length'
                    ? 'max_tokens'
                    : 'end_turn'

              controller.enqueue(
                encoder.encode(
                  makeAnthropicSSE('message_delta', {
                    type: 'message_delta',
                    delta: {
                      stop_reason: stopReason,
                      stop_sequence: null,
                    },
                    usage: { output_tokens: outputTokens },
                  }),
                ),
              )
              controller.enqueue(
                encoder.encode(
                  makeAnthropicSSE('message_stop', {
                    type: 'message_stop',
                  }),
                ),
              )
              controller.close()
              return
            }
          }
        }
        // Stream ended without [DONE] or finish_reason
        if (contentBlockStarted) {
          controller.enqueue(
            encoder.encode(
              makeAnthropicSSE('content_block_stop', {
                type: 'content_block_stop',
                index: blockIndex,
              }),
            ),
          )
        }
        controller.enqueue(
          encoder.encode(
            makeAnthropicSSE('message_delta', {
              type: 'message_delta',
              delta: { stop_reason: 'end_turn', stop_sequence: null },
              usage: { output_tokens: outputTokens },
            }),
          ),
        )
        controller.enqueue(
          encoder.encode(
            makeAnthropicSSE('message_stop', { type: 'message_stop' }),
          ),
        )
        controller.close()
      } catch (err) {
        controller.error(err)
      }
    },
  })
}

// ─── Non-streaming: OpenAI response → Anthropic response ─────────────────────

function convertOpenAIResponseToAnthropic(
  openaiResp: {
    id?: string
    choices?: Array<{
      message?: {
        content?: string | null
        tool_calls?: Array<{
          id: string
          function: { name: string; arguments: string }
        }>
      }
      finish_reason?: string
    }>
    usage?: { prompt_tokens?: number; completion_tokens?: number }
  },
  model: string,
): unknown {
  const choice = openaiResp.choices?.[0]
  const content: unknown[] = []

  if (choice?.message?.content) {
    content.push({ type: 'text', text: choice.message.content })
  }

  if (choice?.message?.tool_calls) {
    for (const tc of choice.message.tool_calls) {
      let input: unknown = {}
      try {
        input = JSON.parse(tc.function.arguments)
      } catch {
        input = { raw: tc.function.arguments }
      }
      content.push({
        type: 'tool_use',
        id: tc.id,
        name: tc.function.name,
        input,
      })
    }
  }

  const stopReason =
    choice?.finish_reason === 'tool_calls'
      ? 'tool_use'
      : choice?.finish_reason === 'length'
        ? 'max_tokens'
        : 'end_turn'

  return {
    id: openaiResp.id || `msg_${Date.now()}`,
    type: 'message',
    role: 'assistant',
    content,
    model,
    stop_reason: stopReason,
    stop_sequence: null,
    usage: {
      input_tokens: openaiResp.usage?.prompt_tokens || 100,
      output_tokens: openaiResp.usage?.completion_tokens || 1,
      cache_creation_input_tokens: 0,
      cache_read_input_tokens: 0,
    },
  }
}

// ─── Main: Create Ollama fetch adapter ───────────────────────────────────────

export function createOllamaFetch(
  ollamaBaseUrl: string,
  ollamaModel: string,
  ollamaApiKey?: string,
): typeof globalThis.fetch {
  // Strip trailing slashes and /v1 suffix if present, then always append /v1/chat/completions
  const defaultBase = ollamaBaseUrl.replace(/\/+$/, '').replace(/\/v1$/i, '')
  const defaultUrl = `${defaultBase}/v1/chat/completions`

  return async (
    input: RequestInfo | URL,
    init?: RequestInit,
  ): Promise<Response> => {
    // Only intercept POST requests to messages endpoint
    const url = typeof input === 'string' ? input : input instanceof URL ? input.href : (input as Request).url
    const isMessagesEndpoint =
      url.includes('/messages') && init?.method?.toUpperCase() === 'POST'

    if (!isMessagesEndpoint || !init?.body) {
      // Pass through non-messages requests
      return globalThis.fetch(input, init)
    }

    // Dynamic model/url/key override from environment (supports runtime switching)
    const runtimeBaseUrl = process.env.OLLAMA_BASE_URL_RUNTIME
    const runtimeModel = process.env.OLLAMA_MODEL_RUNTIME || ollamaModel
    const runtimeApiKey = process.env.OLLAMA_API_KEY_RUNTIME || ollamaApiKey
    let activeUrl = defaultUrl
    if (runtimeBaseUrl) {
      const base = runtimeBaseUrl.replace(/\/+$/, '').replace(/\/v1$/i, '')
      activeUrl = `${base}/v1/chat/completions`
    }

    // Parse Anthropic request
    let anthropicReq: AnthropicRequest
    try {
      anthropicReq = JSON.parse(
        typeof init.body === 'string' ? init.body : new TextDecoder().decode(init.body as BufferSource),
      )
    } catch {
      return globalThis.fetch(input, init)
    }

    const isStreaming = anthropicReq.stream === true

    // Convert to OpenAI format
    const openaiMessages = convertMessages(
      anthropicReq.messages,
      anthropicReq.system,
    )
    const openaiTools = convertTools(anthropicReq.tools)

    const openaiReq: Record<string, unknown> = {
      model: runtimeModel,
      messages: openaiMessages,
      max_tokens: anthropicReq.max_tokens,
      stream: isStreaming,
    }
    if (anthropicReq.temperature !== undefined) {
      openaiReq.temperature = anthropicReq.temperature
    }
    if (anthropicReq.top_p !== undefined) {
      openaiReq.top_p = anthropicReq.top_p
    }
    if (anthropicReq.stop_sequences) {
      openaiReq.stop = anthropicReq.stop_sequences
    }
    if (openaiTools) {
      openaiReq.tools = openaiTools
    }

    // Send to Ollama
    const headers: Record<string, string> = { 'Content-Type': 'application/json' }
    if (runtimeApiKey) {
      headers['Authorization'] = `Bearer ${runtimeApiKey}`
    }
    const ollamaResp = await globalThis.fetch(activeUrl, {
      method: 'POST',
      headers,
      body: JSON.stringify(openaiReq),
      signal: init.signal || undefined,
    })

    if (!ollamaResp.ok) {
      const errText = await ollamaResp.text()
      return new Response(
        JSON.stringify({
          type: 'error',
          error: {
            type: 'api_error',
            message: `Ollama error (${ollamaResp.status}): ${errText}`,
          },
        }),
        {
          status: ollamaResp.status,
          headers: {
            'content-type': 'application/json',
            'request-id': `ollama_${Date.now()}`,
          },
        },
      )
    }

    if (isStreaming) {
      // Convert OpenAI SSE stream → Anthropic SSE stream
      const anthropicStream = buildAnthropicStreamFromOpenAI(
        ollamaResp.body!,
        runtimeModel,
      )
      return new Response(anthropicStream, {
        status: 200,
        headers: {
          'content-type': 'text/event-stream',
          'request-id': `ollama_${Date.now()}`,
        },
      })
    } else {
      // Non-streaming: convert response format
      const openaiResult = await ollamaResp.json()
      const anthropicResult = convertOpenAIResponseToAnthropic(
        openaiResult,
        runtimeModel,
      )
      return new Response(JSON.stringify(anthropicResult), {
        status: 200,
        headers: {
          'content-type': 'application/json',
          'request-id': `ollama_${Date.now()}`,
        },
      })
    }
  }
}
