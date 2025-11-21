import React from 'react';
import { Button } from '../ui/Button';

export function ApprovalPrompt({ approval, onApprove, onReject, disabled }) {
  return (
    <div className="border-t border-gray-200 bg-yellow-50">
      <div className="max-w-3xl mx-auto p-4">
        <div className="mb-2 text-sm text-yellow-800 font-medium">Pending approval required</div>
        <pre className="whitespace-pre-wrap text-sm bg-white border border-yellow-200 rounded p-3 overflow-auto max-h-64">{approval?.draft || approval?.content || 'Review the draft content above.'}</pre>
        <div className="mt-3 flex gap-2">
          <Button onClick={() => onApprove('yes')} disabled={disabled}>Approve</Button>
          <Button variant="secondary" onClick={() => onReject('no')} disabled={disabled}>Reject</Button>
        </div>
      </div>
    </div>
  );
}
