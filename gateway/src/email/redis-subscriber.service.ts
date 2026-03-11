import { Injectable, OnModuleInit, OnModuleDestroy, Logger } from '@nestjs/common';
import Redis from 'ioredis';
import { EmailService } from './email.service';

@Injectable()
export class RedisSubscriberService implements OnModuleInit, OnModuleDestroy {
  private readonly logger = new Logger(RedisSubscriberService.name);
  private subscriber: Redis;

  constructor(private readonly emailService: EmailService) {}

  onModuleInit() {
    this.subscriber = new Redis(process.env.REDIS_URL || 'redis://localhost:6379');
    this.subscriber.subscribe('email:send');
    this.subscriber.on('message', async (_channel: string, message: string) => {
      try {
        const payload = JSON.parse(message);
        this.logger.log(`Received email:send for ${payload.to}`);
        await this.emailService.sendWorkspaceEmail(payload);
      } catch (err) {
        this.logger.error('Failed to send email from pub/sub event', err);
      }
    });
    this.logger.log('Subscribed to email:send');
  }

  async onModuleDestroy() {
    await this.subscriber.quit();
  }
}
