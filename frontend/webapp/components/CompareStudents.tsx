'use client';

import { useState } from 'react';
import { Card, Input, Button, Space, Alert, Spin, Typography, message } from 'antd';
import { LineChartOutlined, LoadingOutlined } from '@ant-design/icons';
import ReactECharts from 'echarts-for-react';
import { useI18n } from './I18nContext';
import { getApiBaseUrl } from '../utils/apiBase';

const { Title, Text } = Typography;
const { TextArea } = Input;

interface Student {
  id: string;
  username: string;
  url: string[];
  pq_id: string;
}

interface StudentsInput {
  students: Student[];
}

interface TrajectoryScore {
  [key: string]: number | null;
}

interface TrajectoryEvaluation {
  scores: TrajectoryScore;
}

interface TrajectoryCheckpoint {
  evaluation: TrajectoryEvaluation;
}

interface TrajectoryData {
  checkpoints: TrajectoryCheckpoint[];
}

interface PQActivity {
  ranking_position: number;
  total_participants: number;
  accuracy_rate: number;
}

interface StudentData {
  id: string;
  name: string;
  trajectoryScores: number[];
  runnerScores: number[];
  pqScores: number[];
  combinedScores: number[];
}

// Hardcoded PQ API key
const PQ_API_KEY = 'BbjiZsAwDnLNwqXCFRLztOtZfP-0OrfU7nUsykW4s2Y';

export default function CompareStudents() {
  const { t } = useI18n();
  const [jsonInput, setJsonInput] = useState(`{
  "students": [
    {
      "id": "student_1",
      "username": "lexicalmathical",
      "url": ["https://github.com/shuxueshuxue/ink-and-memory"],
      "pq_id": "JUFV4ZFT"
    }
  ]
}`);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [studentsData, setStudentsData] = useState<StudentData[]>([]);
  const [maxCheckpoints, setMaxCheckpoints] = useState(0);

  // Validate JSON input
  const validateJSON = (input: string): StudentsInput | null => {
    try {
      const parsed = JSON.parse(input);

      if (!parsed.students || !Array.isArray(parsed.students)) {
        throw new Error('JSON must contain a "students" array');
      }

      for (const student of parsed.students) {
        if (!student.id || typeof student.id !== 'string') {
          throw new Error('Each student must have a valid "id" string');
        }
        if (!student.username || typeof student.username !== 'string') {
          throw new Error('Each student must have a valid "username" string');
        }
        if (!student.url || !Array.isArray(student.url) || student.url.length === 0) {
          throw new Error('Each student must have a "url" array with at least one URL');
        }
        if (!student.pq_id || typeof student.pq_id !== 'string') {
          throw new Error('Each student must have a valid "pq_id" string');
        }
      }

      return parsed;
    } catch (err) {
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError('Invalid JSON format');
      }
      return null;
    }
  };

  // Calculate average of non-null values
  const calculateAverage = (values: (number | null)[]): number => {
    const validValues = values.filter((v): v is number =>
      v !== null && v !== undefined && !isNaN(v) && isFinite(v)
    );
    if (validValues.length === 0) return 0;
    return validValues.reduce((sum, val) => sum + val, 0) / validValues.length;
  };

  // Calculate PQ score from ranking
  const calculatePQScore = (rankingPosition: number, totalParticipants: number): number => {
    // More explicit null/undefined checking
    if (rankingPosition === null || rankingPosition === undefined ||
        totalParticipants === null || totalParticipants === undefined ||
        totalParticipants === 0) {
      console.log('[PQ Score] Invalid input:', { rankingPosition, totalParticipants });
      return 0;
    }
    const score = ((totalParticipants - rankingPosition + 1) / totalParticipants) * 100;
    console.log('[PQ Score] Calculated:', { rankingPosition, totalParticipants, score });
    return score;
  };

  // Align array to target length by filling with average
  const alignToLength = (arr: number[], targetLength: number): number[] => {
    if (arr.length === 0) {
      return new Array(targetLength).fill(0);
    }

    if (arr.length >= targetLength) {
      return arr.slice(0, targetLength);
    }

    const average = calculateAverage(arr);
    const result = [...arr];
    while (result.length < targetLength) {
      result.push(average);
    }
    return result;
  };

  // Fetch trajectory data
  const fetchTrajectoryData = async (repoUrl: string, author: string): Promise<number[]> => {
    try {
      const apiBase = getApiBaseUrl();
      const url = `${apiBase}/api/trajectory/analyze?plugin=zgc_simple&model=anthropic/claude-sonnet-4.5&use_cache=true`;

      const response = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          username: author,
          repo_urls: [repoUrl],
          aliases: [author]
        })
      });

      if (!response.ok) {
        console.error(`Trajectory API failed for ${author}: ${response.statusText}`);
        return [];
      }

      const result = await response.json();
      if (!result.success || !result.trajectory?.checkpoints) {
        return [];
      }

      const checkpoints: TrajectoryCheckpoint[] = result.trajectory.checkpoints;
      const trajectoryScores = checkpoints.map(cp => {
        if (!cp.evaluation || !cp.evaluation.scores) {
          return 0;
        }
        const scores = Object.values(cp.evaluation.scores).filter((v): v is number =>
          v !== null && v !== undefined && !isNaN(v) && isFinite(v)
        );
        return scores.length > 0 ? calculateAverage(scores) : 0;
      });
      console.log(`[Trajectory] ${author} scores:`, trajectoryScores);
      return trajectoryScores;
    } catch (err) {
      console.error(`Failed to fetch trajectory for ${author}:`, err);
      return [];
    }
  };

  // Parse SSE stream and extract final score
  const parseSSEStream = async (response: Response): Promise<number> => {
    const reader = response.body?.getReader();
    if (!reader) {
      throw new Error('No response body');
    }

    const decoder = new TextDecoder();
    let buffer = '';

    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const eventData = JSON.parse(line.slice(6));
              if (eventData.event === 'status' && eventData.data?.status === 'completed') {
                return eventData.data.results?.score || 0;
              }
              if (eventData.event === 'progress') {
                console.log(`[Runner Progress] ${eventData.data.message}`);
              }
            } catch (e) {
              // Skip malformed JSON
            }
          }
        }
      }
    } finally {
      reader.releaseLock();
    }

    return 0; // No score found
  };

  // Fetch runner data - runs repository tests and returns score
  const fetchRunnerData = async (repoUrl: string): Promise<number> => {
    try {
      const apiBase = getApiBaseUrl();
      console.log(`[Runner] Starting test execution for ${repoUrl}`);

      // Step 1: Clone repository
      console.log('[Runner] Step 1/3: Cloning repository...');
      const cloneResponse = await fetch(`${apiBase}/api/runner/clone`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ repo_url: repoUrl })
      });

      if (!cloneResponse.ok) {
        console.error(`[Runner] Clone failed: ${cloneResponse.statusText}`);
        return 0;
      }

      const cloneData = await cloneResponse.json();
      const { clone_path } = cloneData;
      console.log(`[Runner] Cloned to: ${clone_path}`);

      // Step 2: Explore repository (generates REPO_OVERVIEW.md)
      console.log('[Runner] Step 2/3: Exploring repository...');
      const exploreResponse = await fetch(`${apiBase}/api/runner/explore`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ clone_path })
      });

      if (!exploreResponse.ok) {
        console.error(`[Runner] Explore failed: ${exploreResponse.statusText}`);
        return 0;
      }

      // Wait for exploration to complete (SSE stream)
      let overviewPath = '';
      const exploreReader = exploreResponse.body?.getReader();
      if (exploreReader) {
        const decoder = new TextDecoder();
        let buffer = '';

        try {
          while (true) {
            const { done, value } = await exploreReader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n');
            buffer = lines.pop() || '';

            for (const line of lines) {
              if (line.startsWith('data: ')) {
                try {
                  const eventData = JSON.parse(line.slice(6));
                  if (eventData.event === 'status' && eventData.data?.status === 'completed') {
                    overviewPath = eventData.data.overview_path;
                  }
                } catch (e) {
                  // Skip malformed JSON
                }
              }
            }
          }
        } finally {
          exploreReader.releaseLock();
        }
      }

      console.log(`[Runner] Overview generated: ${overviewPath}`);

      // Step 3: Run tests (SSE stream with final score)
      console.log('[Runner] Step 3/3: Running tests...');
      const runTestsResponse = await fetch(`${apiBase}/api/runner/run-tests`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ clone_path, overview_path: overviewPath })
      });

      if (!runTestsResponse.ok) {
        console.error(`[Runner] Run tests failed: ${runTestsResponse.statusText}`);
        return 0;
      }

      // Parse SSE stream to get final score
      const score = await parseSSEStream(runTestsResponse);
      console.log(`[Runner] ${repoUrl} final score: ${score}`);
      return score;

    } catch (err) {
      console.error(`[Runner] Failed to fetch runner data for ${repoUrl}:`, err);
      return 0;
    }
  };

  // Fetch PQ data
  const fetchPQData = async (pqId: string): Promise<number[]> => {
    try {
      const apiBase = getApiBaseUrl();
      const [userId, seriesName] = pqId.includes('|') ? pqId.split('|') : [pqId, 'vibe-coding-2026-3'];

      const url = `${apiBase}/api/external/query-score?external_user_id=${encodeURIComponent(userId)}&series_name=${encodeURIComponent(seriesName)}`;

      const response = await fetch(url, {
        headers: {
          'X-API-Key': PQ_API_KEY,
          'Content-Type': 'application/json',
        }
      });

      if (!response.ok) {
        console.error(`PQ API failed for ${pqId}: ${response.statusText}`);
        return [];
      }

      const result = await response.json();
      if (!result.success || !result.data?.activities) {
        return [];
      }

      const activities: PQActivity[] = result.data.activities;
      const pqScores = activities.map(activity =>
        calculatePQScore(activity.ranking_position, activity.total_participants)
      );
      console.log(`[PQ] ${pqId} scores:`, pqScores);
      return pqScores;
    } catch (err) {
      console.error(`Failed to fetch PQ data for ${pqId}:`, err);
      return [];
    }
  };

  // Compare students
  const handleCompare = async () => {
    const validated = validateJSON(jsonInput);
    if (!validated) return;

    setLoading(true);
    setError(null);
    setStudentsData([]);

    try {
      const allStudentsData: StudentData[] = [];
      let maxLen = 0;

      // Fetch data for each student
      for (const student of validated.students) {
        message.info(`Fetching data for ${student.username}...`);

        // For simplicity, use first URL
        const repoUrl = student.url[0];

        // Extract author name from repo or use student username
        const author = student.username;

        // Fetch all three data sources (runner is mocked)
        const [trajectoryScores, runnerScore, pqScores] = await Promise.all([
          fetchTrajectoryData(repoUrl, author),
          fetchRunnerData(repoUrl),
          fetchPQData(student.pq_id)
        ]);

        maxLen = Math.max(maxLen, trajectoryScores.length, pqScores.length, 1);

        allStudentsData.push({
          id: student.id,
          name: student.username,
          trajectoryScores,
          runnerScores: [runnerScore],
          pqScores,
          combinedScores: []
        });
      }

      // Align all data to the same length
      const alignedStudentsData = allStudentsData.map(student => {
        console.log(`\n[Align] Student ${student.name}:`);
        console.log('  Original trajectory:', student.trajectoryScores);
        console.log('  Original runner:', student.runnerScores);
        console.log('  Original PQ:', student.pqScores);

        const alignedTrajectory = alignToLength(student.trajectoryScores, maxLen);
        const alignedRunner = alignToLength(student.runnerScores, maxLen);
        const alignedPQ = alignToLength(student.pqScores, maxLen);

        console.log('  Aligned trajectory:', alignedTrajectory);
        console.log('  Aligned runner:', alignedRunner);
        console.log('  Aligned PQ:', alignedPQ);

        // Calculate combined scores (sum of three aspects)
        const combinedScores = alignedTrajectory.map((t, i) => {
          // Ensure all components are valid numbers
          const trajScore = isNaN(t) || !isFinite(t) ? 0 : t;
          const runnerScore = isNaN(alignedRunner[i]) || !isFinite(alignedRunner[i]) ? 0 : alignedRunner[i];
          const pqScore = isNaN(alignedPQ[i]) || !isFinite(alignedPQ[i]) ? 0 : alignedPQ[i];

          const score = trajScore + runnerScore + pqScore;
          console.log(`  Checkpoint ${i + 1}: ${trajScore} + ${runnerScore} + ${pqScore} = ${score}`);

          // Final safety check
          return isNaN(score) || !isFinite(score) ? 0 : score;
        });

        console.log('  Combined scores:', combinedScores);

        return {
          ...student,
          trajectoryScores: alignedTrajectory,
          runnerScores: alignedRunner,
          pqScores: alignedPQ,
          combinedScores
        };
      });

      setStudentsData(alignedStudentsData);
      setMaxCheckpoints(maxLen);
      message.success(t('compare_students.comparison_complete'));
    } catch (err) {
      console.error('Comparison failed:', err);
      setError(err instanceof Error ? err.message : 'Failed to compare students');
    } finally {
      setLoading(false);
    }
  };

  // Generate chart option
  const getChartOption = () => {
    if (studentsData.length === 0) return {};

    const xAxisData = Array.from({ length: maxCheckpoints }, (_, i) => `${i + 1}`);

    return {
      title: {
        text: t('compare_students.chart_title'),
        left: 'center'
      },
      tooltip: {
        trigger: 'axis',
        formatter: (params: any) => {
          let result = `<strong>${t('compare_students.checkpoint')} ${params[0].name}</strong><br/>`;
          params.forEach((param: any) => {
            const value = isNaN(param.value) ? 0 : param.value;
            result += `${param.marker} ${param.seriesName}: ${value.toFixed(2)}<br/>`;
          });
          return result;
        }
      },
      legend: {
        data: studentsData.map(s => s.name),
        bottom: 10,
        type: 'scroll'
      },
      xAxis: {
        type: 'category',
        data: xAxisData,
        name: t('compare_students.xaxis'),
        nameLocation: 'middle',
        nameGap: 30
      },
      yAxis: {
        type: 'value',
        name: t('compare_students.yaxis'),
        nameLocation: 'middle',
        nameGap: 50
      },
      series: studentsData.map(student => ({
        name: student.name,
        type: 'line',
        smooth: true,
        data: student.combinedScores,
        emphasis: {
          focus: 'series'
        }
      }))
    };
  };

  return (
    <div style={{ padding: '24px', maxWidth: '1400px', margin: '0 auto' }}>
      <Title level={2}>{t('compare_students.title')}</Title>
      <Text type="secondary">{t('compare_students.description')}</Text>

      {/* Input Form */}
      <Card style={{ marginTop: '24px', marginBottom: '24px' }}>
        <Space direction="vertical" size="large" style={{ width: '100%' }}>
          <div>
            <Text strong style={{ display: 'block', marginBottom: '8px' }}>
              {t('compare_students.input_label')}
            </Text>
            <TextArea
              rows={10}
              placeholder={t('compare_students.input_placeholder')}
              value={jsonInput}
              onChange={(e) => setJsonInput(e.target.value)}
              disabled={loading}
              style={{ fontFamily: 'monospace' }}
            />
          </div>

          <Button
            type="primary"
            size="large"
            icon={loading ? <LoadingOutlined /> : <LineChartOutlined />}
            onClick={handleCompare}
            loading={loading}
            disabled={!jsonInput.trim()}
          >
            {loading ? t('compare_students.comparing') : t('compare_students.compare_button')}
          </Button>
        </Space>
      </Card>

      {/* Error Display */}
      {error && (
        <Alert
          message={t('compare_students.error')}
          description={error}
          type="error"
          closable
          onClose={() => setError(null)}
          style={{ marginBottom: '24px' }}
        />
      )}

      {/* Loading Indicator */}
      {loading && (
        <Card style={{ marginBottom: '24px' }}>
          <div style={{ textAlign: 'center', padding: '40px' }}>
            <Spin size="large" />
            <div style={{ marginTop: '16px' }}>
              <Text>{t('compare_students.loading')}</Text>
            </div>
          </div>
        </Card>
      )}

      {/* Chart Display */}
      {!loading && studentsData.length > 0 && (
        <Card title={t('compare_students.results_title')}>
          <ReactECharts
            option={getChartOption()}
            style={{ height: '500px' }}
            opts={{ renderer: 'canvas' }}
            notMerge={true}
            lazyUpdate={true}
          />
        </Card>
      )}
    </div>
  );
}
