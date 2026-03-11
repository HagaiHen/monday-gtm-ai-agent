import { Module } from '@nestjs/common';
import { EmailController } from './email.controller';
import { EmailService } from './email.service';
import { RedisSubscriberService } from './redis-subscriber.service';

@Module({
  controllers: [EmailController],
  providers: [EmailService, RedisSubscriberService],
})
export class EmailModule {}
