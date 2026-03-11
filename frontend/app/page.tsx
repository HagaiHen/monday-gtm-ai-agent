'use client';

import { useState } from 'react';
import LeadForm from './components/LeadForm';
import ChatUI from './components/ChatUI';
import DoneScreen from './components/DoneScreen';

type Screen = 'form' | 'chat' | 'done';

interface LeadData {
  sessionId: string;
  name: string;
  email: string;
  company: string;
  website: string;
  industry: string;
  painPoint: string;
  teamSize: string;
}

export default function Page() {
  const [screen, setScreen] = useState<Screen>('form');
  const [leadData, setLeadData] = useState<LeadData | null>(null);

  return (
    <div style={{ minHeight: '100vh' }}>
      {screen === 'form' && (
        <LeadForm
          onSubmit={(data) => {
            setLeadData(data);
            setScreen('chat');
          }}
        />
      )}
      {screen === 'chat' && leadData && (
        <ChatUI
          sessionId={leadData.sessionId}
          name={leadData.name}
          onDone={() => setScreen('done')}
        />
      )}
      {screen === 'done' && <DoneScreen name={leadData?.name || ''} />}
    </div>
  );
}
