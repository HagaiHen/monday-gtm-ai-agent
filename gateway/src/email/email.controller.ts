import { Controller, Post, Body } from '@nestjs/common';
import { EmailService } from './email.service';

@Controller('email')
export class EmailController {
  constructor(private readonly emailService: EmailService) {}

  @Post('send')
  async sendEmail(
    @Body()
    body: {
      to: string;
      name: string;
      board_url: string;
      board_name: string;
      company_summary: string;
      columns: string[];
      item_names: string[];
      dashboard_url?: string;
      dashboard_widgets?: string[];
      team_size?: number;
    },
  ) {
    await this.emailService.sendWorkspaceEmail(body);
    return { success: true };
  }
}
