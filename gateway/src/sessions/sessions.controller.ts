import { Controller, Post, Body, BadRequestException } from '@nestjs/common';
import { SessionsService } from './sessions.service';

@Controller('sessions')
export class SessionsController {
  constructor(private readonly sessionsService: SessionsService) {}

  @Post()
  async createSession(
    @Body()
    body: {
      name: string;
      email: string;
      company: string;
      website?: string;
      industry: string;
      pain_point: string;
      team_size: number;
    },
  ) {
    const { name, email, company, website, industry, pain_point, team_size } = body;
    if (!name || !email || !company || !industry || !pain_point || !team_size) {
      throw new BadRequestException('name, email, company, industry, pain_point, and team_size are required');
    }
    const session = await this.sessionsService.createSession(
      name,
      email,
      company,
      website || '',
      industry,
      pain_point,
      Number(team_size),
    );
    return { session_id: session.session_id };
  }
}
