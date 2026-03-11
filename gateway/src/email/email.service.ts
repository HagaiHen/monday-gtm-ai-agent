import { Injectable } from '@nestjs/common';
import * as nodemailer from 'nodemailer';

interface WorkspaceEmailPayload {
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
}

// Mock URLs
const PURCHASE_URL = 'https://monday.com/pricing';
const MEETING_URL  = 'https://calendly.com/monday-sales/30min';

function recommendPlan(teamSize: number): { name: string; pricePerSeat: number; color: string } {
  if (teamSize > 50) return { name: 'Enterprise', pricePerSeat: 0,  color: '#6C5CE7' };
  if (teamSize > 10) return { name: 'Pro',        pricePerSeat: 19, color: '#6C5CE7' };
  return                     { name: 'Standard',  pricePerSeat: 12, color: '#6C5CE7' };
}

@Injectable()
export class EmailService {
  private transporter: nodemailer.Transporter;

  constructor() {
    this.transporter = nodemailer.createTransport({
      host: process.env.SMTP_HOST || 'mailpit',
      port: parseInt(process.env.SMTP_PORT || '1025'),
      secure: false,
    });
  }

  async sendWorkspaceEmail(payload: WorkspaceEmailPayload): Promise<void> {
    const { to, name, board_url, board_name, company_summary, columns, item_names, dashboard_url, dashboard_widgets, team_size } = payload;
    const seats = Math.max(team_size || 0, 3);
    const plan  = recommendPlan(seats);
    const monthlyTotal = plan.pricePerSeat > 0 ? `$${plan.pricePerSeat * seats}/mo` : 'Custom pricing';

    console.log(`[Email] Sending to: ${to}`);
    console.log(`[Email] Board: ${board_name} → ${board_url}`);
    console.log(`[Email] Columns: ${(columns || []).join(', ')}`);
    console.log(`[Email] Items: ${(item_names || []).join(', ')}`);
    const firstName = name.split(' ')[0];

    const columnPills = columns
      .map(
        (col) =>
          `<span style="display:inline-block;background:#EDE9FD;color:#5A4BD1;padding:4px 10px;border-radius:20px;font-size:12px;font-weight:500;margin:3px 3px 3px 0">${col}</span>`,
      )
      .join('');

    const itemRows = item_names
      .map(
        (item) =>
          `<tr>
            <td style="padding:10px 12px;border-bottom:1px solid #F1F3F5;font-size:14px;color:#343A40">
              <span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:#6C5CE7;margin-right:10px;vertical-align:middle"></span>
              ${item}
            </td>
            <td style="padding:10px 12px;border-bottom:1px solid #F1F3F5">
              <span style="display:inline-block;background:#D4EDDA;color:#155724;font-size:11px;padding:2px 8px;border-radius:10px">Ready</span>
            </td>
          </tr>`,
      )
      .join('');

    const html = `
<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#F4F5F7;font-family:'Segoe UI',Arial,sans-serif">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#F4F5F7;padding:40px 0">
    <tr><td align="center">
      <table width="600" cellpadding="0" cellspacing="0" style="background:#fff;border-radius:16px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,0.08)">

        <!-- Header -->
        <tr>
          <td style="background:linear-gradient(135deg,#6C5CE7,#a29bfe);padding:40px 48px;text-align:center">
            <div style="display:inline-block;background:rgba(255,255,255,0.2);border-radius:12px;padding:10px 20px;margin-bottom:20px">
              <span style="color:#fff;font-size:22px;font-weight:700;letter-spacing:-0.5px">monday.com</span>
            </div>
            <h1 style="color:#fff;margin:0;font-size:28px;font-weight:700">Your workspace is live!</h1>
            <p style="color:rgba(255,255,255,0.85);margin:10px 0 0;font-size:15px">We built a board tailored just for ${firstName}'s team</p>
          </td>
        </tr>

        <!-- Body -->
        <tr><td style="padding:40px 48px">

          <p style="margin:0 0 8px;font-size:16px;color:#212529">Hi ${firstName},</p>
          <p style="margin:0 0 28px;font-size:15px;color:#6C757D;line-height:1.6">${company_summary}</p>

          <!-- Board card -->
          <div style="border:1.5px solid #E9ECEF;border-radius:12px;overflow:hidden;margin-bottom:28px">
            <div style="background:#FAFAFA;padding:16px 20px;border-bottom:1px solid #E9ECEF;display:flex;align-items:center;gap:12px">
              <span style="font-size:18px">📋</span>
              <span style="font-weight:600;font-size:15px;color:#212529">${board_name}</span>
            </div>
            <div style="padding:16px 20px;border-bottom:1px solid #E9ECEF">
              <p style="margin:0 0 10px;font-size:12px;font-weight:600;color:#ADB5BD;text-transform:uppercase;letter-spacing:0.5px">Columns</p>
              <div>${columnPills}</div>
            </div>
            <div style="padding:16px 20px;text-align:center">
              <a href="${board_url}" style="display:inline-block;background:#6C5CE7;color:#fff;padding:14px 36px;border-radius:10px;text-decoration:none;font-size:15px;font-weight:600;letter-spacing:-0.2px">
                Open my board →
              </a>
              <p style="margin:12px 0 0;font-size:12px;color:#ADB5BD">
                Or copy this link: <a href="${board_url}" style="color:#6C5CE7">${board_url}</a>
              </p>
            </div>
          </div>

          ${dashboard_url ? `
          <!-- Dashboard card -->
          <div style="border:1.5px solid #E9ECEF;border-radius:12px;overflow:hidden;margin-bottom:28px">
            <div style="background:#FAFAFA;padding:16px 20px;border-bottom:1px solid #E9ECEF;display:flex;align-items:center;gap:12px">
              <span style="font-size:18px">📊</span>
              <span style="font-weight:600;font-size:15px;color:#212529">${board_name} — Overview</span>
            </div>
            ${dashboard_widgets && dashboard_widgets.length > 0 ? `
            <div style="padding:16px 20px;border-bottom:1px solid #E9ECEF">
              <p style="margin:0 0 10px;font-size:12px;font-weight:600;color:#ADB5BD;text-transform:uppercase;letter-spacing:0.5px">Widgets</p>
              <div>${dashboard_widgets.map(w =>
                `<span style="display:inline-block;background:#E6F9F1;color:#037f4c;padding:4px 10px;border-radius:20px;font-size:12px;font-weight:500;margin:3px 3px 3px 0">${w}</span>`
              ).join('')}</div>
            </div>
            ` : ''}
            <div style="padding:16px 20px;text-align:center">
              <a href="${dashboard_url}" style="display:inline-block;background:#00c875;color:#fff;padding:14px 36px;border-radius:10px;text-decoration:none;font-size:15px;font-weight:600;letter-spacing:-0.2px">
                View my dashboard →
              </a>
              <p style="margin:12px 0 0;font-size:12px;color:#ADB5BD">
                Or copy this link: <a href="${dashboard_url}" style="color:#00c875">${dashboard_url}</a>
              </p>
            </div>
          </div>
          ` : ''}

          <!-- Pricing -->
          <div style="border:1.5px solid #E9ECEF;border-radius:12px;overflow:hidden;margin-bottom:28px">
            <div style="background:#FAFAFA;padding:16px 20px;border-bottom:1px solid #E9ECEF;display:flex;align-items:center;gap:12px">
              <span style="font-size:18px">💳</span>
              <span style="font-weight:600;font-size:15px;color:#212529">Ready to make it official?</span>
            </div>
            <div style="padding:20px 24px">
              <p style="margin:0 0 16px;font-size:14px;color:#6C757D;line-height:1.6">
                Based on your team of <strong>${seats} people</strong>, we recommend the
                <strong style="color:#6C5CE7">${plan.name} plan</strong>${plan.pricePerSeat > 0 ? ` — billed at <strong>${monthlyTotal}</strong> (annual)` : ''}.
              </p>
              <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:16px">
                <tr>
                  ${plan.pricePerSeat > 0 ? `
                  <td style="padding:12px 16px;background:#F8F6FF;border-radius:8px;text-align:center">
                    <div style="font-size:11px;color:#ADB5BD;text-transform:uppercase;letter-spacing:0.5px;margin-bottom:4px">Per seat / month</div>
                    <div style="font-size:22px;font-weight:700;color:#6C5CE7">$${plan.pricePerSeat}</div>
                    <div style="font-size:11px;color:#ADB5BD">billed annually</div>
                  </td>
                  <td width="16"></td>
                  <td style="padding:12px 16px;background:#F8F6FF;border-radius:8px;text-align:center">
                    <div style="font-size:11px;color:#ADB5BD;text-transform:uppercase;letter-spacing:0.5px;margin-bottom:4px">Your team total</div>
                    <div style="font-size:22px;font-weight:700;color:#6C5CE7">${monthlyTotal}</div>
                    <div style="font-size:11px;color:#ADB5BD">${seats} seats × $${plan.pricePerSeat}</div>
                  </td>` : `
                  <td style="padding:12px 16px;background:#F8F6FF;border-radius:8px;text-align:center">
                    <div style="font-size:14px;color:#6C757D">Enterprise pricing is tailored to your team's needs.</div>
                  </td>`}
                </tr>
              </table>
              <table cellpadding="0" cellspacing="0" style="margin:0 auto">
                <tr>
                  <td style="padding-right:10px">
                    <a href="${PURCHASE_URL}" style="display:inline-block;background:#6C5CE7;color:#fff;padding:13px 28px;border-radius:8px;text-decoration:none;font-size:14px;font-weight:600">
                      Start ${plan.name} plan →
                    </a>
                  </td>
                  <td>
                    <a href="${MEETING_URL}" style="display:inline-block;background:#fff;color:#6C5CE7;padding:12px 28px;border-radius:8px;text-decoration:none;font-size:14px;font-weight:600;border:2px solid #6C5CE7">
                      📅 Talk to our team
                    </a>
                  </td>
                </tr>
              </table>
              <p style="margin:14px 0 0;font-size:12px;color:#ADB5BD;text-align:center">
                Not sure which plan fits? We'll walk you through it — no commitment needed.
              </p>
            </div>
          </div>

          <!-- Get to know us -->
          <div style="border:1.5px solid #E9ECEF;border-radius:12px;overflow:hidden;margin-bottom:28px">
            <div style="background:#FAFAFA;padding:16px 20px;border-bottom:1px solid #E9ECEF">
              <span style="font-size:18px">🎬</span>
              <span style="font-weight:600;font-size:15px;color:#212529;margin-left:8px">Want to see what monday.com can really do?</span>
            </div>
            <div style="padding:20px 24px;text-align:center">
              <p style="margin:0 0 16px;font-size:14px;color:#6C757D;line-height:1.6">
                Watch how teams like yours use monday.com to manage work, hit goals, and stay aligned — all in one place.
              </p>
              <a href="https://www.youtube.com/watch?v=mZwt56r3-KA"
                 style="display:inline-block;background:#FF0000;color:#fff;padding:12px 28px;border-radius:8px;text-decoration:none;font-size:14px;font-weight:600">
                ▶ Watch on YouTube
              </a>
            </div>
          </div>

        </td></tr>

        <!-- Footer -->
        <tr>
          <td style="background:#F8F9FA;padding:24px 48px;text-align:center;border-top:1px solid #E9ECEF">
            <p style="margin:0;font-size:13px;color:#ADB5BD">
              You're receiving this because you signed up for a monday.com workspace demo.<br>
              © 2025 monday.com — Where work gets done.
            </p>
          </td>
        </tr>

      </table>
    </td></tr>
  </table>
</body>
</html>`;

    let info: any;
    try {
    info = await this.transporter.sendMail({
      from: '"monday.com" <noreply@monday-demo.com>',
      to,
      subject: `${firstName}, your "${board_name}" board is ready 🎉`,
      html,
    });
    console.log(`[Email] Sent OK — messageId: ${info.messageId}`);
    } catch (err) {
      console.error(`[Email] FAILED:`, err);
      throw err;
    }
  }
}
