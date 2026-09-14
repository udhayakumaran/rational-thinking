import * as fs from 'fs';
import * as path from 'path';
import * as os from 'os';
import * as dotenv from 'dotenv';
import type { Scene, ScriptData } from '../src/utils/scriptParser';

dotenv.config({ override: true });

function isScriptData(obj: unknown): obj is ScriptData {
  if (typeof obj !== 'object' || obj === null) return false;
  const data = obj as Record<string, unknown>;
  return (
    typeof data.title === 'string' &&
    typeof data.topic === 'string' &&
    Array.isArray(data.scenes) &&
    data.scenes.every(isScene)
  );
}

function isScene(obj: unknown): obj is Scene {
  if (typeof obj !== 'object' || obj === null) return false;
  const scene = obj as Record<string, unknown>;
  const validTypes = ['question_scene', 'narrative_scene', 'experiment_scene', 'interactive_scene', 'reflection_scene'];
  return (
    validTypes.includes(scene.type as string) &&
    typeof scene.title === 'string' &&
    typeof scene.voiceover === 'string' &&
    (scene.duration === undefined || typeof scene.duration === 'number') &&
    (scene.description === undefined || typeof scene.description === 'string')
  );
}

const API_KEY_PRIMARY = process.env.API_KEY_PRIMARY || process.env.OPENROUTER_API_KEY;
const API_KEY_FALLBACK = process.env.API_KEY_FALLBACK;
const LLM_MODEL_PRIMARY: string = process.env.LLM_MODEL_PRIMARY || process.env.OPENROUTER_MODEL || 'auto';
const LLM_ENDPOINT_PRIMARY: string = process.env.LLM_ENDPOINT_PRIMARY || 'https://openrouter.ai/api/v1/chat/completions';
const LLM_ENDPOINT_FALLBACK: string | undefined = process.env.LLM_ENDPOINT_FALLBACK;
const LLM_MODEL_FALLBACK: string | undefined = process.env.LLM_MODEL_FALLBACK;

if (!API_KEY_PRIMARY && !API_KEY_FALLBACK) {
  console.error('Error: No API key configured. Set API_KEY_PRIMARY (or OPENROUTER_API_KEY) or API_KEY_FALLBACK in .env');
  process.exit(1);
}

async function generateScript(topic: string): Promise<ScriptData> {
  const prompt = `You are a scriptwriter for an educational YouTube channel called "Rational Thinking". Create a detailed JSON script for a video about "${topic}".

The script should have 5-7 scenes. Each scene must be one of these types:
- question_scene: Opens with curiosity, poses questions (blue/purple gradient)
- narrative_scene: Provides historical/contextual information (light gray background)
- experiment_scene: Describes evidence or observations (dark background)
- interactive_scene: Encourages viewer participation (pink/red gradient)
- reflection_scene: Closing thoughts on limitations or implications (dark purple gradient)

CRITICAL: Output ONLY valid JSON, no markdown, no explanations.

JSON format:
{
  "title": "Video Title",
  "topic": "${topic}",
  "scenes": [
    {
      "type": "question_scene",
      "title": "Title for this scene",
      "voiceover": "Spoken text for narrator",
      "duration": 5
    },
    ...
  ]
}

Each scene:
- type: Must be one of the 5 types above
- title: 5-15 words max
- voiceover: 20-100 words, conversational tone
- duration: 4-8 seconds typical
- description: (optional) Extra visual context for experiment_scene

Respond with ONLY the JSON object.`;

  if (API_KEY_PRIMARY) {
    return generateViaPrimary(prompt);
  } else if (API_KEY_FALLBACK) {
    return generateViaFallback(prompt);
  } else {
    throw new Error('No API key found. Set API_KEY_PRIMARY or API_KEY_FALLBACK in .env');
  }
}

interface LLMResponse {
  error?: { message: string };
  choices?: Array<{
    message: { content: string };
  }>;
  content?: Array<{ text: string }>;
}

async function generateViaPrimary(prompt: string): Promise<ScriptData> {
  if (!API_KEY_PRIMARY) {
    throw new Error('API_KEY_PRIMARY is not set');
  }

  const response = await fetch(LLM_ENDPOINT_PRIMARY, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${API_KEY_PRIMARY}`,
      'Content-Type': 'application/json',
      'HTTP-Referer': 'https://rational-thinking.local',
      'User-Agent': 'Rational Thinking Video Generator',
    },
    body: JSON.stringify({
      model: LLM_MODEL_PRIMARY,
      messages: [{ role: 'user', content: prompt }],
      temperature: 0.7,
      max_tokens: 2000,
    }),
  });

  const parsed: LLMResponse = await response.json();

  if (!response.ok) {
    if (parsed.error) {
      throw new Error(`LLM error: ${parsed.error.message}`);
    }
    throw new Error(`LLM HTTP ${response.status}: ${JSON.stringify(parsed)}`);
  }

  let content: string;
  if (parsed.choices?.[0]?.message?.content) {
    content = parsed.choices[0].message.content.trim();
  } else if (parsed.content?.[0]?.text) {
    content = parsed.content[0].text.trim();
  } else {
    throw new Error(`Invalid response structure: ${JSON.stringify(parsed).substring(0, 200)}`);
  }

  const jsonMatch = content.match(/\{[\s\S]*\}/);
  if (!jsonMatch) {
    throw new Error('No JSON found in response');
  }

  const parsed_script = JSON.parse(jsonMatch[0]) as unknown;
  if (!isScriptData(parsed_script)) {
    throw new Error('Invalid script data structure');
  }
  return parsed_script;
}

async function generateViaFallback(prompt: string): Promise<ScriptData> {
  if (!API_KEY_FALLBACK) {
    throw new Error('API_KEY_FALLBACK is not set');
  }

  if (!LLM_ENDPOINT_FALLBACK) {
    throw new Error('LLM_ENDPOINT_FALLBACK is not configured');
  }

  const response = await fetch(LLM_ENDPOINT_FALLBACK, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${API_KEY_FALLBACK}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      model: LLM_MODEL_FALLBACK,
      max_tokens: 2000,
      messages: [{ role: 'user', content: prompt }],
    }),
  });

  const parsed: LLMResponse = await response.json();

  if (!response.ok) {
    if (parsed.error) {
      throw new Error(`LLM error: ${parsed.error.message}`);
    }
    throw new Error(`LLM HTTP ${response.status}: ${JSON.stringify(parsed)}`);
  }

  let content: string;
  if (parsed.content?.[0]?.text) {
    content = parsed.content[0].text.trim();
  } else if (parsed.choices?.[0]?.message?.content) {
    content = parsed.choices[0].message.content.trim();
  } else {
    throw new Error(`Invalid response structure: ${JSON.stringify(parsed).substring(0, 200)}`);
  }

  const jsonMatch = content.match(/\{[\s\S]*\}/);
  if (!jsonMatch) {
    throw new Error('No JSON found in response');
  }

  const parsed_script = JSON.parse(jsonMatch[0]) as unknown;
  if (!isScriptData(parsed_script)) {
    throw new Error('Invalid script data structure');
  }
  return parsed_script;
}

function getOptimalConcurrency(): number {
  const override = process.env.RENDER_CONCURRENCY;
  if (override) {
    const parsed = parseInt(override, 10);
    if (!isNaN(parsed) && parsed > 0) return parsed;
  }
  const cpuCount = os.cpus().length;
  // Use 80% of available cores, leave some for system
  return Math.max(2, Math.floor(cpuCount * 0.8));
}

async function renderVideo(
  scriptData: ScriptData,
  outputPath: string
): Promise<void> {
  // Write to src/ so components can import it
  const generatedScriptPath = path.join(process.cwd(), 'src', 'generated-script.json');
  fs.writeFileSync(generatedScriptPath, JSON.stringify(scriptData, null, 2));

  const outDir = path.dirname(outputPath);
  if (!fs.existsSync(outDir)) {
    fs.mkdirSync(outDir, { recursive: true });
  }

  try {
    const { bundle } = await import('@remotion/bundler');
    const { renderMedia } = await import('@remotion/renderer');
    const concurrency = getOptimalConcurrency();

    console.log(`Bundling (concurrency: ${concurrency})...`);
    const bundleLocation = await bundle(
      path.join(process.cwd(), 'src', 'video-root.tsx'),
      undefined,
      {
        webpackOverride: (config) => config,
      }
    );

    const durationInFrames = Math.ceil(
      scriptData.scenes.reduce((acc, s) => acc + (s.duration || 5), 0) * 30
    );

    console.log(`Rendering ${durationInFrames} frames...`);

    let lastLoggedPercent = -1;

    await (renderMedia as (cfg: unknown) => Promise<unknown>)({
      composition: {
        id: 'VideoComp',
        width: 1280,
        height: 720,
        fps: 30,
        durationInFrames,
      } as any,
      serveUrl: bundleLocation,
      outputLocation: outputPath,
      codec: 'h264',
      inputProps: { scriptData },
      concurrency,
      jpegQuality: 90,
      overwrite: true,
      onProgress: (progress: any) => {
        const pct = Math.floor(progress.progress * 100);
        if (pct > lastLoggedPercent) {
          console.log(`[${pct}%] Rendered: ${progress.renderedFrames} frames`);
          lastLoggedPercent = pct;
        }
      },
    });

    console.log('\n✓ Video rendered: ' + outputPath);

    if (fs.existsSync(outputPath)) {
      const stats = fs.statSync(outputPath);
      console.log(`File size: ${(stats.size / 1024 / 1024).toFixed(2)}MB`);
    } else {
      throw new Error(`Output file not created: ${outputPath}`);
    }
  } catch (error) {
    throw new Error(`Failed to render video: ${error}`);
  }
}

async function main() {
  const topic = process.argv[2];

  if (!topic) {
    console.error('Usage: npx ts-node scripts/generate.ts "<topic>"');
    process.exit(1);
  }

  console.log(`Generating script for: ${topic}`);

  try {
    const scriptData = await generateScript(topic);
    console.log(`✓ Script generated: ${scriptData.scenes.length} scenes`);

    const sanitizedTopic = topic
      .toLowerCase()
      .replace(/[^\w\s-]/g, '')
      .replace(/\s+/g, '-')
      .replace(/-+/g, '-')
      .replace(/^-|-$/g, '');
    const filename = `${sanitizedTopic}-${Date.now()}.mp4`;
    const outputPath = path.join(process.cwd(), 'out', 'videos', filename);

    console.log(`Rendering video to: ${outputPath}`);
    await renderVideo(scriptData, outputPath);

    console.log(`✓ Video rendered successfully: ${outputPath}`);
  } catch (error) {
    console.error('Error:', error);
    process.exit(1);
  }
}

main();
