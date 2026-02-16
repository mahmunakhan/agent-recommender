const API_BASE_URL = 'http://localhost:8000';

export interface LoginRequest {
  email: string;
  password: string;
}

export interface RegisterRequest {
  email: string;
  password: string;
  role: 'candidate' | 'recruiter';
  first_name: string;
  last_name: string;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
}

export interface User {
  id: string;
  email: string;
  role: string;
  first_name: string;
  last_name: string;
}

export interface Profile {
  id: string;
  headline: string;
  summary: string;
  location_city: string;
  location_country: string;
  years_experience: number;
  desired_role: string;
  desired_salary_min: number;
  desired_salary_max: number;
  is_open_to_work: boolean;
  is_verified: boolean;
  skills: ProfileSkill[];
  parsed_json_draft?: any;
}

export interface ProfileSkill {
  skill_id: string;
  skill_name: string;
  proficiency_level: string;
  years_experience: number;
  is_primary: boolean;
}

export interface Job {
  id: string;
  title: string;
  company_name: string;
  description_raw?: string;
  location_city: string;
  location_country: string;
  location_type: string;
  employment_type: string;
  salary_min: number;
  salary_max: number;
  salary_currency?: string;
  experience_min_years: number;
  experience_max_years?: number;
  is_active: boolean;
  posted_at: string;
  posted_by_id?: string;
  skills?: JobSkill[];
}

export interface Application {
  id: string;
  user_id: string;
  job_id: string;
  status: string;
  cover_letter?: string;
  source: string;
  match_score_at_apply?: number;
  recruiter_notes?: string;
  rejection_reason?: string;
  applied_at: string;
  status_updated_at: string;
  job_title?: string;
  company_name?: string;
  location_city?: string;
  location_country?: string;
  employment_type?: string;
  applicant_name?: string;
  applicant_email?: string;
  headline?: string;
  years_experience?: number;
}

export interface JobSkill {
  skill_id: string;
  skill_name: string;
  requirement_type: string;
  min_years?: number;
}

export interface Skill {
  id: string;
  name: string;
  slug: string;
  skill_type: string;
  category_id?: string;
}

export interface Recommendation {
  id: number;
  match_score: number;
  skill_match_score: number;
  experience_match_score: number;
  location_match_score: number;
  job: Job;
  recommendation_reason?: string;
  ranking_position: number;
  matched_skills: string[];
  missing_skills: string[];
  is_viewed: boolean;
  user_feedback?: string;
}


export interface Notification {
  id: string;
  notification_type: string;
  title: string;
  message: string;
  action_url?: string;
  priority: string;
  is_read: boolean;
  created_at: string;
}

class ApiClient {
  private token: string | null = null;

  setToken(token: string) {
    this.token = token;
    if (typeof window !== 'undefined') {
      localStorage.setItem('token', token);
    }
  }

  getToken(): string | null {
    if (!this.token && typeof window !== 'undefined') {
      this.token = localStorage.getItem('token');
    }
    return this.token;
  }

  clearToken() {
    this.token = null;
    if (typeof window !== 'undefined') {
      localStorage.removeItem('token');
    }
  }

  logout() {
    this.clearToken();
  }

  private getHeaders(): HeadersInit {
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
    };
    const token = this.getToken();
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }
    return headers;
  }

  private async request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
    const headers: HeadersInit = {
      'Content-Type': 'application/json',
      ...options.headers,
    };

    const token = this.getToken();
    if (token) {
      (headers as Record<string, string>)['Authorization'] = 'Bearer ' + token;
    }

    const response = await fetch(API_BASE_URL + endpoint, {
      ...options,
      headers,
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Request failed' }));
      throw new Error(error.detail || 'Request failed');
    }

    return response.json();
  }

  // Auth methods
  async login(data: LoginRequest): Promise<AuthResponse> {
    const response = await this.request<AuthResponse>('/auth/login', {
      method: 'POST',
      body: JSON.stringify(data),
    });
    this.setToken(response.access_token);
    return response;
  }

  async register(data: RegisterRequest): Promise<User> {
    return this.request<User>('/auth/register', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async getMe(): Promise<User> {
    return this.request<User>('/auth/me');
  }

  // Profile methods
  async getProfile(): Promise<Profile> {
    return this.request<Profile>('/profiles/me');
  }

  async updateProfile(data: Partial<Profile>): Promise<{ message: string }> {
    return this.request('/profiles/me', {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  }

  async addSkill(data: { skill_id: string; proficiency_level: string; years_experience?: number; is_primary?: boolean }): Promise<{ message: string }> {
    return this.request('/profiles/me/skills', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async removeSkill(skillId: string): Promise<{ message: string }> {
    return this.request('/profiles/me/skills/' + skillId, {
      method: 'DELETE',
    });
  }

  async uploadResume(file: File): Promise<{ message: string; s3_path: string; parsed: boolean }> {
    const formData = new FormData();
    formData.append('file', file);

    const token = this.getToken();
    const headers: HeadersInit = {};
    if (token) {
      headers['Authorization'] = 'Bearer ' + token;
    }

    const response = await fetch(API_BASE_URL + '/profiles/me/resume', {
      method: 'POST',
      headers,
      body: formData,
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Upload failed' }));
      throw new Error(error.detail || 'Upload failed');
    }

    return response.json();
  }

  // Job methods - Read
  async getJobs(params?: { search?: string; location?: string; page?: number }): Promise<Job[]> {
    const searchParams = new URLSearchParams();
    if (params?.search) searchParams.append('search', params.search);
    if (params?.location) searchParams.append('location', params.location);
    if (params?.page) searchParams.append('page', params.page.toString());

    const query = searchParams.toString();
    const response = await this.request<{ jobs: Job[] } | Job[]>('/jobs/' + (query ? '?' + query : ''));

    if (Array.isArray(response)) {
      return response;
    }
    return response.jobs || [];
  }

  async getJob(id: string): Promise<Job> {
    return this.request<Job>('/jobs/' + id);
  }

  async searchJobsSemantic(query: string): Promise<{ jobs: (Job & { similarity_score: number })[] }> {
    return this.request('/jobs/search/semantic?query=' + encodeURIComponent(query));
  }

  // Job methods - Create, Update, Delete (for recruiters)
  async createJob(jobData: Partial<Job>): Promise<Job> {
    return this.request<Job>('/jobs/', {
      method: 'POST',
      body: JSON.stringify(jobData),
    });
  }

  async updateJob(jobId: string, jobData: Partial<Job>): Promise<Job> {
    return this.request<Job>('/jobs/' + jobId, {
      method: 'PUT',
      body: JSON.stringify(jobData),
    });
  }

  async deleteJob(jobId: string): Promise<void> {
    await this.request('/jobs/' + jobId, {
      method: 'DELETE',
    });
  }

  async addJobSkill(jobId: string, skillId: string, requirementType: string): Promise<any> {
    return this.request('/jobs/' + jobId + '/skills', {
      method: 'POST',
      body: JSON.stringify({
        skill_id: skillId,
        requirement_type: requirementType,
      }),
    });
  }

  async removeJobSkill(jobId: string, skillId: string): Promise<void> {
    await this.request('/jobs/' + jobId + '/skills/' + skillId, {
      method: 'DELETE',
    });
  }

  // Recruiter methods - Get my posted jobs
  async getMyJobs(): Promise<{ jobs: Job[]; total: number }> {
    return this.request('/jobs/recruiter/my-jobs');
  }

  // Application methods - Candidate
  async applyToJob(jobId: string, coverLetter?: string, source: string = 'direct'): Promise<Application> {
    return this.request<Application>('/applications', {
      method: 'POST',
      body: JSON.stringify({
        job_id: jobId,
        cover_letter: coverLetter,
        source: source,
      }),
    });
  }

  async getMyApplications(status?: string): Promise<{ applications: Application[]; total: number }> {
    const query = status ? '?status=' + status : '';
    return this.request('/applications/my-applications' + query);
  }

  async checkApplicationStatus(jobId: string): Promise<{ applied: boolean; application_id?: string; status?: string; applied_at?: string }> {
    return this.request('/applications/check/' + jobId);
  }

  async withdrawApplication(applicationId: string): Promise<{ message: string }> {
    return this.request('/applications/' + applicationId, {
      method: 'DELETE',
    });
  }

  // Application methods - Recruiter
  async getJobApplications(jobId: string, status?: string): Promise<{ applications: Application[]; total: number; status_counts: Record<string, number> }> {
    const query = status ? '?status=' + status : '';
    return this.request('/applications/job/' + jobId + query);
  }

  async updateApplication(applicationId: string, data: { status?: string; recruiter_notes?: string; rejection_reason?: string }): Promise<Application> {
    return this.request<Application>('/applications/' + applicationId, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  }

  async getAllRecruiterApplications(status?: string): Promise<{ applications: Application[]; total: number }> {
    const query = status ? '?status=' + status : '';
    return this.request('/applications/recruiter/all' + query);
  }

  // Recommendation methods
  async getRecommendations(): Promise<{ recommendations: Recommendation[] }> {
    return this.request('/recommendations/jobs');
  }

  async getAILearningPath(): Promise<any> {
    return this.request('/recommendations/ai-learning-path');
  }

  async getLearningPath(): Promise<{ learning_path: any[], total_items: number }> {
    return this.request('/recommendations/learning-path');
  }

  async getSkillGaps(): Promise<{ skill_gaps: any[] }> {
    return this.request('/recommendations/skill-gaps');
  }

  // Skills taxonomy methods
  async getSkills(params?: { page?: number; category?: string }): Promise<Skill[]> {
    const searchParams = new URLSearchParams();
    if (params?.page) searchParams.append('page', params.page.toString());
    if (params?.category) searchParams.append('category_id', params.category);

    const query = searchParams.toString();
    const response = await this.request<{ skills: Skill[] } | Skill[]>('/skills/' + (query ? '?' + query : ''));

    if (Array.isArray(response)) {
      return response;
    }
    return response.skills || [];
  }

  async getSkillCategories(): Promise<{ categories: any[] }> {
    return this.request('/skills/categories');
  }
  // Notification methods
  async getNotifications(unreadOnly: boolean = false): Promise<Notification[]> {
    const params = unreadOnly ? '?unread_only=true' : '';
    return this.request('/notifications' + params);
  }

  async getUnreadCount(): Promise<{ unread_count: number }> {
    return this.request('/notifications/count');
  }

  async markNotificationRead(notificationId: string): Promise<{ message: string }> {
    return this.request('/notifications/' + notificationId + '/read', { method: 'POST' });
  }

  async markAllNotificationsRead(): Promise<{ message: string }> {
    return this.request('/notifications/read-all', { method: 'POST' });
  }
}
export const api = new ApiClient();
export default api;





