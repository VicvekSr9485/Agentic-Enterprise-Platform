import React, { useState } from 'react';
import { Header } from './components/layout/Header';
import { Sidebar } from './components/layout/Sidebar';
import { MessageList } from './components/chat/MessageList';
import { ChatInput } from './components/chat/ChatInput';
import { ApprovalPrompt } from './components/chat/ApprovalPrompt';
import { Button } from './components/ui/Button';
import { useChat } from './hooks/useChat';
import { generateSessionId } from './utils/helpers';

function App() {
  const [sessionId, setSessionId] = useState(() => generateSessionId());
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const { messages, isLoading, sendMessage, clearMessages, pendingApproval } = useChat(sessionId);

  const handleNewSession = () => {
    clearMessages();
    const newSessionId = generateSessionId();
    setSessionId(newSessionId);
  };

  const handleApproval = async (response) => {
    await sendMessage(response);
  };

  return (
    <div className="flex h-screen overflow-hidden bg-gradient-to-br from-slate-50 via-blue-50 to-indigo-50">
      <Sidebar isOpen={sidebarOpen} onClose={() => setSidebarOpen(false)} onNewSession={handleNewSession} />

      <div className="flex-1 flex flex-col overflow-hidden">
        <Header onMenuClick={() => setSidebarOpen(true)} />

        <div className="flex-1 flex flex-col overflow-hidden relative">
          <MessageList messages={messages} isLoading={isLoading} />

          {pendingApproval && (
            <ApprovalPrompt
              approval={pendingApproval}
              onApprove={handleApproval}
              onReject={handleApproval}
              disabled={isLoading}
            />
          )}

          {!pendingApproval && (
            <ChatInput
              onSendMessage={sendMessage}
              disabled={isLoading}
            />
          )}
        </div>
      </div>
    </div>
  );
}

export default App;
