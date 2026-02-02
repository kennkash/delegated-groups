    /* -------------------------------------------------------
        confGroups()
       ------------------------------------------------------- */
    async function confGroups() {
        try {
            const { data } = await apiInstance.get('/v0/conf-internal-groups');
            // optional: showToastFromEnvelope(data);
            return data;
        } catch (e) {
            usePageStore().error({
                title: 'axios error: conf_internal_groups',
                code: e.response?.status,
                message: e.message,
            });
        }
    }

    /* -------------------------------------------------------
        jiraGroups()
       ------------------------------------------------------- */
    async function jiraGroups() {
        try {
            const { data } = await apiInstance.get('/v0/jira-internal-groups');
            // optional: showToastFromEnvelope(data);
            return data;
        } catch (e) {
            usePageStore().error({
                title: 'axios error: jira_internal_groups',
                code: e.response?.status,
                message: e.message,
            });
        }
    }
