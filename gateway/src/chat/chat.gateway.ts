import {
  WebSocketGateway,
  WebSocketServer,
  SubscribeMessage,
  MessageBody,
  ConnectedSocket,
  OnGatewayConnection,
  OnGatewayDisconnect,
} from '@nestjs/websockets';
import { Server, Socket } from 'socket.io';
import { SessionsService } from '../sessions/sessions.service';

@WebSocketGateway({
  cors: { origin: '*' },
  namespace: '/chat',
})
export class ChatGateway implements OnGatewayConnection, OnGatewayDisconnect {
  @WebSocketServer()
  server: Server;

  constructor(private readonly sessionsService: SessionsService) {}

  handleConnection(client: Socket) {
    console.log(`Client connected: ${client.id}`);
  }

  handleDisconnect(client: Socket) {
    console.log(`Client disconnected: ${client.id}`);
  }

  @SubscribeMessage('message')
  async handleMessage(
    @MessageBody() data: { session_id: string; content: string },
    @ConnectedSocket() client: Socket,
  ) {
    const { session_id, content } = data;

    const session = await this.sessionsService.getSession(session_id);
    if (!session) {
      client.emit('error', { message: 'Session not found' });
      return;
    }

    if (session.phase === 'done') {
      client.emit('message', {
        role: 'assistant',
        content: 'Your workspace is being prepared. Check your email!',
      });
      client.emit('done', {});
      return;
    }

    try {
      const aiAgentUrl = process.env.AI_SERVICE_URL || 'http://localhost:8000';
      const response = await fetch(`${aiAgentUrl}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id, message: content }),
      });

      if (!response.ok) {
        throw new Error(`AI Agent returned ${response.status}`);
      }

      const result = await response.json();

      client.emit('message', {
        role: 'assistant',
        content: result.reply,
      });

      if (result.phase === 'done') {
        await this.sessionsService.updateSession(session_id, { phase: 'done' });
        client.emit('done', {});
      }
    } catch (err) {
      console.error('Error calling AI agent:', err);
      client.emit('message', {
        role: 'assistant',
        content: 'Sorry, something went wrong. Please try again.',
      });
    }
  }
}
