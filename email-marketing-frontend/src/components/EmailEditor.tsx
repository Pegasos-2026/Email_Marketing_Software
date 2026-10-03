import React, { useState } from 'react';

const EmailEditor: React.FC = () => {
    const [subject, setSubject] = useState<string>('');
    const [body, setBody] = useState<string>('');

    const handleSubjectChange = (event: React.ChangeEvent<HTMLInputElement>) => {
        setSubject(event.target.value);
    };

    const handleBodyChange = (event: React.ChangeEvent<HTMLTextAreaElement>) => {
        setBody(event.target.value);
    };

    const handleSubmit = (event: React.FormEvent) => {
        event.preventDefault();
        // Logic to save the email content goes here
        console.log('Email Subject:', subject);
        console.log('Email Body:', body);
    };

    return (
        <div>
            <h2>Email Editor</h2>
            <form onSubmit={handleSubmit}>
                <div>
                    <label htmlFor="subject">Subject:</label>
                    <input
                        type="text"
                        id="subject"
                        value={subject}
                        onChange={handleSubjectChange}
                        required
                    />
                </div>
                <div>
                    <label htmlFor="body">Body:</label>
                    <textarea
                        id="body"
                        value={body}
                        onChange={handleBodyChange}
                        required
                    />
                </div>
                <button type="submit">Save Email</button>
            </form>
        </div>
    );
};

export default EmailEditor;