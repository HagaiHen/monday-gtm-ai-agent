import { Injectable, OnModuleInit, OnModuleDestroy } from '@nestjs/common';
import Redis from 'ioredis';
import { v4 as uuidv4 } from 'uuid';

export interface SessionData {
  session_id: string;
  name: string;
  email: string;
  company: string;
  website: string;
  industry: string;
  pain_point: string;
  team_size: number;
  phase: 'questioning' | 'building' | 'done';
  created_at: string;
}

@Injectable()
export class SessionsService implements OnModuleInit, OnModuleDestroy {
  private redis: Redis;

  onModuleInit() {
    this.redis = new Redis(process.env.REDIS_URL || 'redis://localhost:6379');
  }

  async onModuleDestroy() {
    await this.redis.quit();
  }

  async createSession(
    name: string,
    email: string,
    company: string,
    website: string,
    industry: string,
    pain_point: string,
    team_size: number,
  ): Promise<SessionData> {
    const session: SessionData = {
      session_id: uuidv4(),
      name,
      email,
      company,
      website,
      industry,
      pain_point,
      team_size,
      phase: 'questioning',
      created_at: new Date().toISOString(),
    };
    await this.redis.set(
      `session:${session.session_id}`,
      JSON.stringify(session),
      'EX',
      86400,
    );
    return session;
  }

  async getSession(session_id: string): Promise<SessionData | null> {
    const data = await this.redis.get(`session:${session_id}`);
    return data ? JSON.parse(data) : null;
  }

  async updateSession(session_id: string, updates: Partial<SessionData>): Promise<void> {
    const session = await this.getSession(session_id);
    if (!session) return;
    const updated = { ...session, ...updates };
    await this.redis.set(`session:${session_id}`, JSON.stringify(updated), 'EX', 86400);
  }
}
