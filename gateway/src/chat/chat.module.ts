import { Module } from '@nestjs/common';
import { ChatGateway } from './chat.gateway';
import { SessionsModule } from '../sessions/sessions.module';

@Module({
  imports: [SessionsModule],
  providers: [ChatGateway],
})
export class ChatModule {}
