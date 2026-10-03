import React, { useEffect, useState } from 'react';
import { useParams, useHistory } from 'react-router-dom';
import { contactService } from '../services/contactService';
import { Contact, ContactList } from '../types';
import '../styles/contacts.css';

const ContactListDetail: React.FC = () => {
    const { listId } = useParams<{ listId: string }>();
    const [contactList, setContactList] = useState<ContactList | null>(null);
    const [contacts, setContacts] = useState<Contact[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');
    const history = useHistory();

    useEffect(() => {
        const fetchList = async () => {
            try {
                setLoading(true);
                const data = await contactService.getContactList(Number(listId));
                setContactList(data);
                setContacts(data.contacts || []);
            } catch (err: any) {
                setError(err.response?.data?.error || 'Failed to load contact list');
            } finally {
                setLoading(false);
            }
        };

        if (listId) fetchList();
    }, [listId]);

    const handleDelete = async () => {
        if (!contactList) return;
        if (window.confirm(`Delete contact list '${contactList.name}'? This will not delete contacts.`)) {
            try {
                await contactService.deleteContactList(contactList.id);
                history.push('/contacts');
            } catch (err: any) {
                setError(err.response?.data?.error || 'Failed to delete contact list');
            }
        }
    };

    if (loading) {
        return <div className="loading">Loading contact list...</div>;
    }

    if (!contactList) {
        return <div className="contacts-container"><p className="error-message">Contact list not found.</p></div>;
    }

    return (
        <div className="contacts-container">
            <div className="contacts-header">
                <div>
                    <h1>{contactList.name}</h1>
                    <p>{contactList.description || 'No description provided.'}</p>
                    <p>{contactList.contact_count} contacts</p>
                </div>
                <div className="header-actions">
                    <button className="btn-secondary" onClick={() => history.push('/contacts')}>
                        Back to Contacts
                    </button>
                    <button className="btn-delete" onClick={handleDelete}>
                        Delete List
                    </button>
                </div>
            </div>

            {error && <div className="error-message">{error}</div>}

            {contacts.length > 0 ? (
                <table className="contacts-table">
                    <thead>
                        <tr>
                            <th>Email</th>
                            <th>Name</th>
                            <th>Status</th>
                        </tr>
                    </thead>
                    <tbody>
                        {contacts.map((contact) => {
                            const isActive = contact.is_subscribed ?? contact.subscribed ?? true;
                            return (
                            <tr key={contact.id}>
                                <td>{contact.email}</td>
                                <td>{contact.name || `${contact.first_name || ''} ${contact.last_name || ''}`.trim()}</td>
                                <td>
                                    <span className={`status-badge ${isActive ? 'subscribed' : 'unsubscribed'}`}>
                                        {isActive ? 'Active' : 'Inactive'}
                                    </span>
                                </td>
                            </tr>
                            );
                        })}
                    </tbody>
                </table>
            ) : (
                <div className="no-data">
                    <p>This contact list has no contacts yet.</p>
                </div>
            )}
        </div>
    );
};

export default ContactListDetail;
