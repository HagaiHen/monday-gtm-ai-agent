import { Module } from '@nestjs/common';
import { SessionsModule } from './sessions/sessions.module';
import { ChatModule } from './chat/chat.module';
import { EmailModule } from './email/email.module';

@Module({
  imports: [SessionsModule, ChatModule, EmailModule],
})
export class AppModule {}
